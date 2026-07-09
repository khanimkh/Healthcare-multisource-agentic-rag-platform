# Guide: `evaluation/` and this project's tooling, configuration, and personal automation

This doc has two parts: what evaluation is actually implemented (not just planned) in this project, and a consolidated, honest inventory of the tooling/configuration/automation actually in place versus not.

---

## 1. What's implemented: `evaluation/`

```text
evaluation/
├── eval_questions.json     -> the golden dataset (question + which chunks should be retrieved)
├── metrics.py               -> pure IR-metric functions, no dependencies on the app
├── evaluate_rag.py          -> loads the dataset, calls RAGAgent.retrieve(), computes + reports metrics
└── evaluation_report.md     -> generated output (overwritten each run)
```

It lives at the **repository root**, as a sibling of `app/` and `tests/` — not inside `app/backend/`. It's a dev-time tool that imports and exercises the app's code; it isn't part of the served API and shouldn't be reachable over HTTP (running it triggers real embedding + OpenSearch calls, which cost money and shouldn't be user-triggerable).

### `metrics.py` — the four retrieval metrics, as pure functions

All four take the same shape of input: a ranked list of retrieved `chunk_id`s (already ordered by score — exactly what `RAGAgent.retrieve()` returns) and a set of `relevant_chunk_id`s from the golden dataset.

| Function | Formula | What it answers |
| --- | --- | --- |
| `precision_at_k(retrieved, relevant, k)` | `(hits in top k) / k` | Of what we returned, how much was actually relevant? |
| `recall_at_k(retrieved, relevant)` | `(hits) / len(relevant)` | Of everything relevant, how much did we find? |
| `reciprocal_rank(retrieved, relevant)` | `1 / rank_of_first_hit` (0 if none) | How far down the list is the *first* correct answer? |
| `ndcg_at_k(retrieved, relevant, k)` | `DCG@k / IDCG@k`, `DCG = Σ 1/log2(rank+1)` for each hit | Does the *ranking order* matter, not just presence? Rewards relevant chunks appearing earlier |

All four are pure functions (no I/O, no app imports) — verified independently of the rest of the app:

```python
precision_at_k(['a','b','c','d','e'], {'b','d'}, 5)   # 0.4
recall_at_k(['a','b','c','d','e'], {'b','d'})          # 1.0
reciprocal_rank(['a','b','c','d','e'], {'b','d'})      # 0.5  (first hit "b" at rank 2)
ndcg_at_k(['a','b','c','d','e'], {'b','d'}, 5)         # 0.651
```

Edge cases are handled without crashing: empty `relevant` set returns `0.0` for recall/NDCG rather than dividing by zero; no hits at all returns `0.0` reciprocal rank.

Relevance here is **binary** (a chunk either is or isn't in `relevant_chunk_ids`) — not graded (0–3 style). That's a deliberate simplification: graded relevance needs a richer labeling effort (rank *how* relevant each chunk is, not just yes/no), and binary is enough to get real signal running before investing in that.

### `eval_questions.json` — the golden dataset, currently a placeholder

```json
[
  {
    "question": "What are the main risk factors for patient readmission?",
    "relevant_chunk_ids": ["REPLACE_WITH_REAL_CHUNK_ID_0", "REPLACE_WITH_REAL_CHUNK_ID_1"]
  }
]
```

The `relevant_chunk_ids` are placeholders. A real `chunk_id` only exists once a document has actually been ingested (`{file_id}_{chunk_index}`, assigned in `OpenSearchVectorStore.index_chunks()`) — there's no ingested data in this dev environment yet, so this file can't be populated with real values until that happens. This is the "golden dataset" blocker flagged earlier as the biggest prerequisite for most evaluation methods.

### `evaluate_rag.py` — the runner

```bash
python -m evaluation.evaluate_rag
```

For every question in `eval_questions.json`, and for each `k` in `(1, 3, 5, 10)`: calls `RAGAgent.retrieve(question, k=k)`, extracts `chunk_id`s, scores them against `relevant_chunk_ids` with all four metric functions, averages across all questions per `k`, and writes a markdown table to `evaluation_report.md` (and prints it).

```text
eval_questions.json
        │
        ▼
for each question, for each k in (1, 3, 5, 10):
        RAGAgent.retrieve(question, k)  -> real embedding + OpenSearch call
                │
                ▼
        precision_at_k / recall_at_k / reciprocal_rank / ndcg_at_k
        │
        ▼
average across all questions, per k
        │
        ▼
evaluation_report.md
```

It imports `RAGAgent` directly from `app.backend.agents.rag_agent` — no retrieval logic is duplicated here; the eval script is a consumer of the real agent code, so it's testing the actual production path, not a reimplementation of it.

**Running it requires live AWS access** (Bedrock for embeddings, OpenSearch for the vector search) — same requirement as running the app itself. It cannot run against fabricated/mocked data as written; see the "not yet implemented" list below for where `moto`-based mocking would change that.

### What this does and doesn't cover, versus the original evaluation list

| From the original "Retrieval Evaluation" list | Status |
| --- | --- |
| Precision@k, Recall@k, MRR, NDCG@k | ✅ Implemented here |
| Top-k optimization | ✅ Implemented as a side effect — `K_VALUES = (1, 3, 5, 10)` already sweeps multiple `k` values in one run; the report table *is* the top-k comparison |
| Context Recall / Context Precision | ❌ Not implemented. These aren't classic IR math — they need either human labeling of "was this chunk actually necessary for the answer" per chunk, or an LLM-as-judge call (reusing `LLMService.generate()` with a grading prompt). Left out of this first pass to keep it dependency-free and deterministic |
| Hybrid retrieval / reranker comparison | ❌ Out of scope for this script — those need the underlying capability (BM25 query path, a reranker) to exist first, which they don't yet |

---

## 2. Tooling, configuration, and personal automation — consolidated, current state

This repeats and updates what came up earlier in conversation, now including the evaluation harness itself.

### Tooling actually wired into the code

FastAPI · LangGraph · AWS Bedrock (via `boto3`, Claude + Titan embeddings) · PostgreSQL + SQLAlchemy · Redis · OpenSearch · AWS S3 / Glue Data Catalog / Athena · spaCy + NetworkX (GraphRAG prototype tier) · Pydantic / pydantic-settings · LangChain text splitters, pypdf, python-docx, Pillow + pytesseract · Python's stdlib `logging` (see below).

### `utils/logger.py` — now implemented, not an empty stub

```python
from app.backend.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("...")
```

`get_logger(name)` returns a `logging.Logger` namespaced under `"app.<name>"`, backed by a single `StreamHandler` attached once to the shared `"app"` logger (a module-level `_CONFIGURED` guard prevents attaching a second handler if `get_logger()` is called many times — verified: `handlers` count stays at 1 across repeated calls). Output format: `timestamp | LEVEL | logger name | message`. No new dependency — plain stdlib `logging`, per the earlier "don't pull in a dependency for something the standard library already does" call.

**Wired into the places identified as the actual gap** (retrieval logs, tool-execution logs), not sprinkled everywhere:

| Layer | What gets logged |
| --- | --- |
| `RouterAgent` | Every routing decision; a `warning` when the model returns an invalid route and it falls back to `"rag"` |
| `SQLAgent` / `S3Agent` | A `warning` when `is_read_only_sql()` rejects a generated query (before it ever reaches Postgres/Athena); row count on successful execution |
| `RAGAgent` | Chunk count retrieved, per call, with `k` |
| `GraphRAGAgent` | Candidate entity count and graph-fact count found per question |
| `SummarizationAgent` | Whether a document was resolved (and which one) or it fell back to the raw question; whether map-reduce triggered; a `warning` if a resolved document has no indexed text |
| `ClassificationAgent` | The resulting category, for both document and structured-dataset classification |
| `FinalAnswerAgent` | Which route the composed answer came from |
| `DocumentIngestionWorkflow` / `StructuredIngestionWorkflow` | Start of ingestion, successful completion (with counts), and an `error`-level log on failure — this is genuinely new signal: failures previously only reached `DocumentStore.update_status(status="failed", ...)` in Postgres, with nothing printed anywhere |
| `QuestionWorkflow` | Every question received (with `session_id`) and which route answered it |
| `api/routes.py` | Upload received/rejected, ask failures — request-level logging at the API boundary |

Deliberately **not** added to `model_service.py`/`embedding_service.py`/`llm_service.py` (the lowest, highest-frequency layer) or to `cache_service.py`/`memory_service.py` (infrastructure-level) — logging every single Bedrock/Redis call would be noisy without adding decision-relevant signal beyond what the agent-level logs above already capture.

### Configuration

- `config/settings.py` — single `Settings` object, everything read from `.env`, nothing hardcoded elsewhere.
- `requirements.txt` — single dependency manifest (unpinned versions), with an inline comment flagging the one manual step pip can't do (`python -m spacy download en_core_web_sm`).
- `docker-compose.yml` exists but references `build: .` with **no `Dockerfile`** present — not currently functional.
- `.gitignore` excludes `.env`, `.venv`, `__pycache__`.

### Personal automation — manual routines, now including the new one

| Routine | What it does | How it's run |
| --- | --- | --- |
| Compile sweep | `python -m py_compile` across `app/` | Manual, before calling any change done |
| Import/dead-code audit | grep every internal import against what's defined; search for orphaned functions and duplicate logic | Manual |
| Doc-per-feature | Every new service/agent gets a `docs/*.md` the same session, including a "known limitations" section | Manual |
| **Retrieval evaluation** *(new)* | `python -m evaluation.evaluate_rag` — scores `RAGAgent` against a golden dataset, writes `evaluation_report.md` | Manual, once `eval_questions.json` has real chunk ids |

None of these are hooked into git (no pre-commit) or CI (no `.github/workflows/`) — they're checklist items I run by hand, not enforced automation. That gap (turning this checklist into an actual pre-commit config) was the top recommendation from the "what personal automation should I add" discussion — still open.

### What's still missing (updated — logging is now off this list)

`tests/` is empty · no CI · no pre-commit hooks · no `Dockerfile` · no token/cost tracking (`ModelService` discards Bedrock's usage data) · no secret scanning (relevant given the `.env` AWS-key exposure found earlier this project) · logging goes to stdout only — no log aggregation/shipping (CloudWatch Logs, etc.) configured yet, since there's no deployment for it to ship from.
