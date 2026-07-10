# Healthcare Multi-Source Agentic RAG Platform — System Design 

## 1. Problem Statement, Use Case

Healthcare organizations store information across disconnected sources — PDF policies, clinical guideline documents, and CSV datasets — and non-technical users need to ask natural-language questions without knowing which source has the answer, how to write SQL, or how to search long documents. This platform lets a user upload documents and CSVs, then ask questions in plain English; a router decides whether the question needs document retrieval, structured-data querying, graph-relationship reasoning, summarization, or classification, and answers with cited sources.

Example questions this system actually answers today (all verified working during this build):

```text
What factors increase the risk of hospital readmission?      -> rag
What is the average age of patients in test_patients?         -> sql
How many rows does the patients dataset have?                 -> s3 (Athena)
Summarize the readmission risk guideline.                     -> summarization
Classify the healthcare insurance policy document.             -> classification
Number of patients by diagnosis (chart)                        -> /visualizations (not chat-routed)
```

---

## 2. What's Actually Built vs. Not

### Business

- **Users**: single-tenant, no accounts. Anyone with access to the running instance can upload and query everything — there's no per-user data isolation.
- **Value**: faster answers from uploaded healthcare documents/CSVs without writing SQL or reading full PDFs, with every answer showing which route handled it and what sources it drew from.
- **Wrong answers**: `FinalAnswerAgent`'s system prompt (`prompts/final_answer_prompt.py`) requires sources + limitations and forbids direct medical advice — this is prompt-level guidance, not a hard technical guardrail. There is no output filtering/validation layer checking that the model actually complied.

### Data

- **Types supported**: CSV (structured), PDF/DOCX/TXT (documents), PNG/JPG/JPEG (OCR'd images). **`.xlsx`/`.xls` are listed as `"structured"` in `detect_file_type()` but have no working loader** — uploading one fails cleanly with `ValueError("Unsupported structured file type: .xlsx")` (see `docs/load-data.md`). `openpyxl` is in `requirements.txt` but currently unused.
- **Sensitivity**: no PII/PHI detection or redaction exists anywhere in the pipeline. Use synthetic/public data only, as the original doc already correctly warned.
- **Update cadence**: manual upload only, one file at a time via drag-and-drop or multi-file select in the browser (`static/index.html`). No scheduled/automated ingestion, no API connectors to external databases.

### Security

- **PII handling**: not implemented (see above).
- **Auth**: not implemented at all — no login, no API keys, no Cognito, no RBAC. `/upload`, `/ask`, `/documents`, `/visualizations` are all open to anyone who can reach the FastAPI server.
- **SQL safety**: real and enforced — `utils/validators.is_read_only_sql()` requires the query to start with `SELECT` and blocks `drop`/`delete`/`update`/`insert`/`alter`/`truncate`/`grant`/`revoke` as whole words (regex `\b`-bounded). Used by both `SQLAgent.execute()` (Postgres) and, transitively, `ChartAgent.build_chart()` (also Postgres, via `SQLAgent`). `S3Agent`/Athena uses the same helper.
- **Credentials**: AWS credentials come from `~/.aws` mounted read-only into the backend container (`docker-compose.yml`), not from AWS Secrets Manager. App config (`Settings` in `config/settings.py`) loads from `.env` via `pydantic-settings`.

### AI design

- **RAG, not fine-tuning** — correct in the original doc, still true.
- **Why agents**: the router (`RouterAgent`) picks one of 6 routes per question based on an LLM call over the available tables/documents/conversation context (`prompts/router_prompt.py`) — see `docs/question-graph-agents-prompts.md` for the full breakdown.
- **Why LangGraph**: `graphs/question_graph.py` is a real compiled `StateGraph` (not hypothetical) — one entry node, a conditional edge dispatching to 6 tool nodes, all converging on a final-answer node. Compiled once at import time.

### Evaluation

**Actually implemented**, not aspirational: `evaluation/evaluate_rag.py` + `evaluation/metrics.py` compute real retrieval metrics (Precision@k, Recall@k, MRR, NDCG@k for k ∈ {1, 3, 5, 10}) against a fixed question set (`evaluation/eval_questions.json`) with known-relevant chunk IDs, writing `evaluation/evaluation_report.md`. A real `tests/` suite exists too (`tests/agents/`, `tests/prompts/`, `tests/schemas/`, `tests/tools/`, `tests/utils/`, `tests/evaluation/`). See `docs/evaluation-and-automation.md` and `docs/testing.md` for the full, already-accurate honest inventory of what's tested/measured versus not — this doc won't duplicate it.

### Production / deployment

**Reality**: `docker-compose.yml` — three containers (`backend`, `postgres:16-alpine`, `redis:7-alpine`), run locally via `docker compose up -d --build`. No ECS, no Fargate, no API Gateway, no Kubernetes, no CI/CD pipeline, no load balancer. The backend container talks to real AWS services (Bedrock, S3, OpenSearch, Glue, Athena) over the internet using mounted local AWS credentials; Postgres and Redis are self-hosted containers, not RDS/ElastiCache.

### Maintenance

- **Updating documents/datasets**: manual upload through the browser UI only.
- **Prompt maintenance**: prompts live as plain Python constants/functions in `prompts/*.py`, version-controlled with the rest of the codebase (i.e., via normal Git history) — there is no separate prompt registry or A/B versioning system.
- **Failure monitoring**: Python's standard `logging` module only (`utils/logger.get_logger(__name__)`), writing to container stdout/`docker compose logs`. No CloudWatch, no X-Ray, no dashboards, no alarms, no cost tracking (cost/token tracking was explicitly considered and deliberately not built).

---

## 3. Data Sources, Loading, Storage — What Actually Happens

### Ingestion entry point

`POST /upload` (`api/routes.py`, see `docs/routers.md`) → `detect_file_type()` (`tools/data_loader.py`, see `docs/load-data.md`) branches to one of two workflows:

```text
"structured" (.csv only — see the .xlsx gap above)
    -> StructuredIngestionWorkflow.ingest_csv()
        -> AWSStorage.upload_file_to_s3()
        -> load_csv() (pandas)
        -> ClassificationAgent.classify_structured_data()
        -> GlueCatalog.register_csv_table()        (Athena-queryable)
        -> RelationalDataStore.load_dataframe()     (Postgres-queryable, dual-write)
        -> DocumentStore: status "registered"

everything else ("document" or "image")
    -> DocumentIngestionWorkflow.ingest()
        -> AWSStorage.upload_file_to_s3()
        -> load_document() (pypdf / python-docx / plain read / pytesseract OCR)
        -> ClassificationAgent.classify_document()
        -> tools/entity_extraction.extract_entities_and_relationships() (spaCy)
        -> GraphStoreService.upsert_edge() per relationship (Postgres graph_nodes/graph_edges)
        -> rag_utils.chunk_documents() -> create_embeddings_for_chunks() (EmbeddingService/Bedrock Titan)
        -> OpenSearchVectorStore.index_chunks() (bulk-indexed, see docs/aws-storage.md)
        -> DocumentStore: status "indexed"
```

Full detail, including the exact call order and known limitations (image files fall into the document branch rather than a distinct path; `load_docx()` doesn't extract table content; deleting a document doesn't clean up its Glue table or graph entries), is in `docs/load-data.md`, `docs/rag-utils.md`, and `docs/RDS-glue.md`.

### Storage, by system

| System | What it actually stores | Real, not RDS/ElastiCache/Neptune |
| --- | --- | --- |
| **Amazon S3** | Raw uploaded files (real AWS S3, via `AWSStorage`) | ✅ real AWS |
| **Amazon OpenSearch** | Document chunks + embeddings, kNN-searchable (`OpenSearchVectorStore`) | ✅ real AWS |
| **AWS Glue Data Catalog** | Table/schema metadata for uploaded CSVs, for Athena (`GlueCatalog`) | ✅ real AWS |
| **Amazon Athena** | Queries CSVs directly from S3 via Glue's catalog (`AthenaService`) | ✅ real AWS |
| **Amazon Bedrock** | Claude Haiku 4.5 (via cross-region inference profile) + Titan Embeddings V2 | ✅ real AWS |
| **Postgres** | App metadata (`documents`, `conversation_messages`, `graph_nodes`, `graph_edges`) **and** dual-written structured data tables (e.g. `test_patients`) | ❌ self-hosted `postgres:16-alpine` container, not RDS |
| **Redis** | Conversation-memory cache (`CacheService`/`MemoryService`, see `docs/cache_memory_service.md`) | ❌ self-hosted `redis:7-alpine` container, not ElastiCache |
| **Knowledge graph** | `graph_nodes`/`graph_edges` Postgres tables, loaded into an in-memory `networkx.MultiDiGraph` per query (`GraphStoreService.find_related()`) | ❌ NetworkX + Postgres prototype, explicitly **not** Amazon Neptune — see the "known limitations" callout in `docs/question-graph-agents-prompts.md` §4 |

### Metadata: two real layers, not three

- **Postgres `documents` table** — file lifecycle (status, timestamps, classified category, error messages). Does **not** store a `glue_table` link back to Glue, despite what the original doc claimed — see `docs/RDS-glue.md` for the real schema and that specific gap.
- **AWS Glue Data Catalog** — table/column/type/S3-location metadata for structured datasets only, used by Athena.

There's no separate "chunk metadata" store beyond OpenSearch itself — each indexed chunk document already carries its own metadata (`file_id`, `chunk_id`, `chunk_index`, `file_name`, `document_type`, `s3_uri`, `uploaded_at`) inline, per `docs/aws-storage.md`.

### Ingestion is synchronous, not async

Every `POST /upload` call blocks until the entire pipeline (S3 upload → classification → extraction → chunking → embedding → indexing) finishes, inside the same FastAPI request. There is no SQS queue, no background worker, no "return immediately, process later" pattern — the original doc's async ingestion diagram doesn't reflect this codebase.

---

## 4. Question-Answering Flow

```text
User asks a question (POST /ask, session_id from browser localStorage)
        │
        ▼
QuestionWorkflow.ask() gathers context:
    SchemaService.describe_tables()  -> Postgres schema (+ one example row per
                                         table, so SQL generation sees real
                                         value formats — see docs/question-
                                         graph-agents-prompts.md §7)
    AthenaService.list_tables()      -> Glue-registered tables
    DocumentStore.list_indexed_document_records() -> for router + resolution
    MemoryService.get_recent_messages(session_id)  -> conversation_context
        │
        ▼
question_graph.invoke(initial_state)   (compiled LangGraph StateGraph)
        │
        ▼
route_question -> RouterAgent.route()  -> one of:
    sql | s3 | rag | graph_rag | summarization | classification
        │
        ▼
    the matching tool node runs its agent, all converge on ->
        │
        ▼
compose_final_answer -> FinalAnswerAgent.compose()
    -> if session_id present, MemoryService.add_message() x2 (user + assistant)
        │
        ▼
{answer, route, sql, sources} returned to the client
```

The full agent-by-agent, prompt-by-prompt breakdown — including the reranking pass in `RAGAgent`, source deduplication, the shared document-resolution helper used by both `SummarizationAgent` and `ClassificationAgent`, and the graph traversal in `GraphRAGAgent` — is in `docs/question-graph-agents-prompts.md`. It is the single most detailed and most current doc in this repo; this section intentionally stays high-level.

**Chart explorer is a separate, unrouted path.** `GET /visualizations/suggestions` and `POST /visualizations` (Insights tab) go through `ChartAgent`/`VisualizationWorkflow` directly — not through `question_graph.py` or `RouterAgent`. Asking for a chart in the main chat box will not currently produce one.

---

## 5. Real Repository Structure

```text
LLM-Healthcare-multisource-agentic-rag-platform/
|
|- app/backend/
|   |- main.py                  FastAPI app, CORS, "/" (frontend), "/health"
|   |- api/routes.py            6 endpoints — see docs/routers.md
|   |- config/settings.py       pydantic-settings, loads .env
|   |- state/state.py           QuestionState TypedDict (LangGraph state)
|   |- graphs/question_graph.py LangGraph StateGraph — see docs/question-graph-agents-prompts.md
|   |- agents/                  9 agents (router, sql, s3, rag, graph_rag,
|   |                           summarization, classification, final_answer, chart)
|   |- prompts/                 one *_prompt.py per agent/task, pure string builders
|   |- services/                model_service, llm_service, embedding_service,
|   |                           aws_storage_service, athena_service, glue_catalog_service,
|   |                           relational_store_service, schema_service, document_store_service,
|   |                           graph_store_service, cache_service, memory_service
|   |- workflows/                document_ingestion_workflow, structured_ingestion_workflow,
|   |                           question_workflow, visualization_workflow
|   |- tools/                   data_loader, rag_utils, document_resolution,
|   |                           entity_extraction (spaCy)
|   |- utils/                   logger, naming, sql_cleanup, validators
|   |- schemas/                 Pydantic request/response models
|   |- static/index.html        the entire frontend — hand-rolled vanilla JS/CSS,
|   |                           no framework, no CDN, no build step. NOT Streamlit.
|   |- data/raw/                transient local upload staging (deleted after ingestion)
|
|- evaluation/                  evaluate_rag.py, metrics.py, eval_questions.json,
|                                evaluation_report.md — real, see docs/evaluation-and-automation.md
|- tests/                       agents/, prompts/, schemas/, tools/, utils/, evaluation/
|- demo/                        app-multisource-agent-rag.mp4 (recorded demo)
|- docs/                        every *.md file referenced throughout this doc
|
|- Dockerfile                   single image, backend only (tesseract-ocr + build-essential + pip)
|- docker-compose.yml           backend + postgres + redis, 3 services total
|- requirements.txt / requirements-dev.txt
|- pytest.ini
|- .env                         (not committed — no .env.example template exists either)
|- README.md
```

There is no `aws/` client-wrapper folder, no `data_pipeline/`, no `storage/`, no `rag/` (chunking/embedding live in `tools/`, not a top-level `rag/`), no `infrastructure/terraform/`, no `frontend/streamlit_app.py`, and no `observability/` folder — all of that was aspirational in the previous version of this doc and doesn't exist in this repository.

---

## 6. Agents and Model Selection

Nine agents, all composing `LLMService` (never `boto3`/`ModelService` directly — see `docs/bedrock-service.md` and `docs/model-service.md` for the full layering): `RouterAgent`, `SQLAgent`, `S3Agent`, `RAGAgent`, `GraphRAGAgent`, `SummarizationAgent`, `ClassificationAgent`, `FinalAnswerAgent`, and `ChartAgent` (the last one outside the routing graph, per §4 above). Full method-by-method detail for each is in `docs/question-graph-agents-prompts.md` §4 — not repeated here.

**Models actually configured** (`config/settings.py`, real defaults):

- **Text generation**: `us.anthropic.claude-haiku-4-5-20251001-v1:0` — note the `us.` prefix: this is a cross-region **inference profile**, required because this Claude model can't be invoked by bare model ID. Not Claude 3.7/3.5 Sonnet, not Llama, not Mistral, not Nova — those were the original doc's aspirational model menu, not what's configured.
- **Embeddings**: `amazon.titan-embed-text-v2:0`.
- **Reranking**: not a separate model — `RAGAgent.rerank_chunks()` reranks via a second Claude call with a numbered-passage prompt (`prompts/rerank_prompt.py`), not Cohere Rerank or a cross-encoder.
- **Graph analytics**: spaCy (entity/relationship extraction) + NetworkX (in-memory traversal) — both real and in active use; Neptune is not used at all.

---

## 7. Running It

```bash
docker compose up -d --build
```

Three containers start: `backend` (port 8000), `postgres` (port 5432), `redis` (port 6379). The frontend is served at `http://localhost:8000/` directly by the FastAPI app (`main.py`'s `serve_frontend()`), not a separate service. `GET /health` returns `{"status": "healthy"}` once the backend is up. There is no separate "local dev" vs. "cloud" environment split — this is the only deployment target that exists today. AWS credentials are picked up from the host's `~/.aws` directory, mounted read-only into the backend container.

There is no CI/CD pipeline, no Terraform/CloudFormation, no ECR, and no automated deployment step of any kind in this repository as of this writing.

---

## 8. Known Gaps (Honest Summary)

Collected from this doc-accuracy pass across the whole `docs/` folder — each of these is a verified, real gap, not speculation:

- `.xlsx`/`.xls` uploads fail — no loader is wired despite being "supported" in `detect_file_type()` (`docs/load-data.md`).
- `DELETE /documents/{file_id}` doesn't clean up the Glue table, knowledge-graph entries, or the Postgres dual-write table for a deleted upload (`docs/routers.md`, `docs/RDS-glue.md`).
- `MemoryService.get_recent_messages()` falls back to Postgres on a Redis cache miss but never writes the result back into the cache (`docs/cache_memory_service.md`).
- The chart explorer (`ChartAgent`) isn't reachable from the main chat — no `chart` route exists in `RouterAgent`/`question_graph.py` (`docs/question-graph-agents-prompts.md` §4).
- No authentication, no PII detection, no per-user data isolation.
- No monitoring/observability beyond stdout logging.

None of these block the MVP from working end-to-end for its intended demo/portfolio use case — they're the honest list of what a genuine production hardening pass would need to address next, in place of the previous doc's already-solved-in-fantasy Cognito/CloudWatch/X-Ray section.
