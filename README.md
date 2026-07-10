# Healthcare Multi-Source Agentic RAG Platform

A FastAPI backend that lets you upload healthcare documents (PDF/DOCX/TXT/images) and CSV datasets, then ask questions in plain English. An LLM-based router decides whether a question needs document retrieval, structured-data SQL, a data-lake query, knowledge-graph reasoning, summarization, or classification — and answers with cited sources.

Built on AWS Bedrock (Claude + Titan Embeddings), OpenSearch, S3, Glue/Athena, and LangGraph, with Postgres and Redis for app state and conversation memory.

> **Note**: this is a portfolio/demo build, not a hardened production system. See [Known Gaps](#known-gaps) below and `docs/system_design_updated.md` for a fully honest account of what is and isn't implemented.

## Example questions

```text
What factors increase the risk of hospital readmission?      -> rag
What is the average age of patients in test_patients?         -> sql
How many rows does the patients dataset have?                 -> s3 (Athena)
Summarize the readmission risk guideline.                     -> summarization
Classify the healthcare insurance policy document.             -> classification
```

## Architecture

```text
POST /upload                                    POST /ask
    │                                                │
    ▼                                                ▼
detect_file_type()                     QuestionWorkflow gathers context
    │                                   (Postgres schema, Glue tables,
    ├── .csv → StructuredIngestionWorkflow            indexed docs, conversation memory)
    │           └─ S3, Glue Catalog, Postgres                     │
    │                                                              ▼
    └── PDF/DOCX/TXT/image → DocumentIngestionWorkflow    question_graph.invoke()
                └─ S3, OCR/parse, classify,               (compiled LangGraph StateGraph)
                   entity/relationship extraction                  │
                   → knowledge graph,                               ▼
                   chunk → embed → index in OpenSearch      RouterAgent picks a route:
                                                             sql | s3 | rag | graph_rag |
                                                             summarization | classification
                                                                     │
                                                                     ▼
                                                         FinalAnswerAgent composes the
                                                         answer with sources, saves to
                                                         conversation memory (Postgres + Redis)
```

Nine agents (router, sql, s3, rag, graph_rag, summarization, classification, final_answer, chart) all reason through a shared `LLMService`, which wraps a single Bedrock Runtime client (`ModelService`). See `docs/system_design_updated.md` for the full design write-up, and the rest of `docs/` for a doc per subsystem (agents/prompts, ingestion, storage, services, evaluation, testing).

## Tech stack

- **API**: FastAPI, served with the frontend as static files (no separate frontend service)
- **Orchestration**: LangGraph (`StateGraph`) for question routing
- **LLM / embeddings**: Amazon Bedrock — Claude Haiku (via cross-region inference profile) for generation, Titan Embeddings V2 for vectors
- **Vector store**: Amazon OpenSearch (kNN)
- **Structured data**: AWS Glue Data Catalog + Athena (query CSVs directly from S3), and a dual-written Postgres copy for direct SQL
- **Knowledge graph**: Postgres-backed nodes/edges, traversed in-memory with NetworkX
- **Object storage**: Amazon S3
- **App state / memory**: Postgres (durable) + Redis (fast conversation-history cache)
- **Document/entity processing**: pypdf, python-docx, pytesseract (OCR), spaCy (entity/relationship extraction)
- **Evaluation**: custom Precision@k / Recall@k / MRR / NDCG@k harness against a fixed question set

## Getting started

### Prerequisites

- Docker and Docker Compose
- An AWS account with access to Bedrock, S3, OpenSearch, Glue, and Athena, configured locally at `~/.aws` (mounted read-only into the backend container)

### Configuration

Create a `.env` file in the project root (there is no committed `.env.example`; the settings below come from `app/backend/config/settings.py`):

Also make sure your AWS credentials (`~/.aws/credentials`) can reach Bedrock, S3, OpenSearch, Glue, and Athena in the configured region.

### Run

```bash
docker compose up -d --build
```

This starts three containers: `backend` (FastAPI, port 8000), `postgres` (port 5432), `redis` (port 6379). The frontend is served directly by the backend at `http://localhost:8000/`.

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

### Run tests / evaluation

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m spacy download en_core_web_sm

pytest

python -m evaluation.evaluate_rag   # requires at least one ingested document, see evaluation/evaluation_report.md
```

## Repository structure

```text
app/backend/
├── main.py            FastAPI app, CORS, "/" (frontend), "/health"
├── api/routes.py       6 HTTP endpoints
├── config/settings.py  pydantic-settings, loads .env
├── graphs/              LangGraph StateGraph for question routing
├── agents/              9 agents (router, sql, s3, rag, graph_rag,
│                        summarization, classification, final_answer, chart)
├── prompts/             one prompt builder per agent/task
├── services/            model/llm/embedding/storage/athena/glue/
│                        relational-store/schema/document-store/
│                        graph-store/cache/memory services
├── workflows/           document & structured ingestion, question, visualization
├── tools/                data loading, chunking, entity extraction (spaCy)
├── utils/                logging, naming, SQL cleanup, validators
├── schemas/              Pydantic request/response models
└── static/index.html     hand-rolled vanilla JS/CSS frontend, no build step

evaluation/    retrieval evaluation harness (Precision@k, Recall@k, MRR, NDCG@k)
tests/         pytest suite (agents, prompts, schemas, tools, utils, evaluation)
demo/          recorded walkthrough video
docs/          detailed per-subsystem design docs
```
