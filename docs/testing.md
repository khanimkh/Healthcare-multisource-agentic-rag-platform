# Guide: testing this project

`tests/` was empty until this pass. This doc explains the three-tier plan, what's actually implemented (Tier 1) versus planned (Tier 2/3), how to run what exists, and a couple of real findings the process surfaced.

---

## 1. Why three tiers, not one flat `tests/` folder

This project's core value is orchestrating external systems — Bedrock, S3, OpenSearch, Postgres, Redis, Glue, Athena. Almost nothing here is testable in true isolation the way a pure algorithm library would be. Rather than write brittle tests that either (a) secretly require live AWS credentials to pass, or (b) mock everything so heavily they stop testing real behavior, the tests are organized by *how much mocking they need*, and each tier is written differently on purpose:

```text
Tier 1  ->  pure logic, no mocking, no live services       (this pass)
Tier 2  ->  mocked AWS/Redis, or SQLite standing in for Postgres   (next)
Tier 3  ->  real FastAPI TestClient against /upload and /ask       (later, needs a working Dockerfile first)
```

---

## 2. Tier 1 — implemented this pass

```text
tests/
├── utils/test_validators.py             (13 tests)
├── evaluation/test_metrics.py           (12 tests)
├── prompts/test_router_prompt.py         (5 tests)
├── prompts/test_sql_prompt.py            (4 tests)
├── prompts/test_rag_prompt.py            (4 tests)
├── prompts/test_graph_rag_prompt.py      (3 tests)
├── prompts/test_summary_prompt.py        (3 tests)
├── prompts/test_classification_prompt.py (4 tests)
├── prompts/test_final_answer_prompt.py   (4 tests)
├── tools/test_data_loader.py             (8 tests)
└── agents/test_summarization_agent.py    (4 tests)
schemas/test_schemas.py                   (6 tests)
```

### What each file actually covers

| File | Tests | Notable case |
| --- | --- | --- |
| `test_validators.py` | Every blocked keyword (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`), case-insensitivity, leading whitespace | **False-positive check**: `SELECT dropout_rate FROM patients` and `SELECT updated_at FROM patients` must *not* be rejected — the keyword match uses `\bword\b` boundaries, so substrings inside column names shouldn't trip it. Verified this actually holds. |
| `test_metrics.py` | Precision@k, Recall@k, MRR, NDCG@k, plus empty-set and zero-hit edge cases, plus a perfect-ranking case (NDCG should hit exactly 1.0) | Uses the exact values hand-verified earlier in this project's evaluation work — now they're assertions, not just chat output |
| `test_*_prompt.py` (7 files) | Every `build_*_prompt()`: interpolates inputs correctly, handles empty/missing optional args without crashing, `ROUTES` list stays in sync with its own system prompt | `test_summary_prompt.py` includes a **regression test** for the map-reduce fix — `build_summary_prompt()` used to hard-truncate at 8000 chars; this test asserts a 10,000-char string passes through untouched, so if that truncation ever creeps back in, this fails |
| `test_data_loader.py` | `detect_file_type()` for every extension category (structured/document/image/unknown), case-insensitivity | See the import-cost finding below |
| `test_summarization_agent.py` | `_resolve_document()`'s word-overlap scoring against real sample filenames (`readmission_risk_guideline.txt`, `lab_result_thresholds.txt`, etc. — the same files generated for manual testing) | See the constructor-coupling finding below |
| `test_schemas.py` | Required-field enforcement and defaults for `QuestionRequest`/`QuestionResponse`/`UploadResponse`, including that both ingestion workflows' actual return shapes validate correctly | Pydantic-only, no app imports needed |

### What was actually verified, honestly

`pytest` itself isn't installed in this dev environment (same limitation flagged throughout this project's build). So instead of just writing files and asserting they'd pass, every test function in `test_validators.py`, `test_metrics.py`, and all seven `test_*_prompt.py` files was executed directly as a plain Python function (they only use `assert`, no pytest-specific features) — **50 test functions, 0 failures**, for real. `test_schemas.py`'s logic was verified the same way, substituting `pytest.raises` with `try/except` for the manual run — **6 for 6**.

`test_data_loader.py` and `test_summarization_agent.py` could **not** be executed here — see below.

---

## 3. Two real findings from actually trying to run these

### Finding 1: heavy module-level imports block testing lightweight functions

`detect_file_type()` in `tools/data_loader.py` is pure, dependency-free logic (just `os.path.splitext`). But the *module* it lives in does `from pypdf import PdfReader`, `from docx import Document`, `from PIL import Image`, `import pytesseract` at the top — unconditionally, even though `detect_file_type()` never calls any of them. Importing the module to test one trivial function requires all four of those packages installed. This is why `test_data_loader.py` couldn't run in this sandbox even though the function it tests has zero real dependencies.

Not fixed here — fixing it would mean making those imports lazy (moved inside the functions that actually use them), which is a real behavior-neutral improvement worth doing, but a separate change from writing the test.

### Finding 2: pure logic trapped behind a heavy constructor

`SummarizationAgent._resolve_document()` doesn't touch `self` at all — it's pure string-matching logic. But calling it normally means constructing a `SummarizationAgent()` first, whose `__init__` builds an `LLMService` and `OpenSearchVectorStore`, both of which need `boto3`/`opensearchpy` importable. The test works around this with `SummarizationAgent.__new__(SummarizationAgent)` — creates the instance without running `__init__` — which is safe here specifically *because* `_resolve_document` never reads instance state. This is a legitimate, known Python testing pattern, but it's also a signal: a class where a "bypass the constructor" trick is needed to test one pure method is a class that could benefit from separating pure logic out from AWS-dependent setup. Noted, not refactored, in this pass.

---

## 4. Tier 2 — planned, not yet implemented

| Target | Mocking approach | What it verifies |
| --- | --- | --- |
| `RouterAgent.route()` | Mock `LLMService.generate()` to return controlled strings | The fallback-to-`"rag"` behavior actually triggers on an invalid model response |
| `SQLAgent.execute()` / `S3Agent.answer()` | Mock `LLMService.generate()` | `is_read_only_sql()` rejection happens *before* the query ever reaches Postgres/Athena — i.e., patch `self.engine.connect()`/`AthenaService.run_query()` and assert they're never called for unsafe SQL |
| `ClassificationAgent` | Mock `LLMService.generate()` | Category string normalization |
| `DocumentStore`, `MemoryService`, `GraphStoreService` | Point `settings.postgres_url` at `sqlite:///:memory:` instead of mocking | Real CRUD logic (status transitions, `GraphStoreService.upsert_node`'s dedup-by-normalized-name) exercised against a real (if different) database, not faked |
| `ModelService` | `moto` or `unittest.mock.patch` on the `boto3` client | Request body construction and response parsing for `invoke_text_model`/`invoke_embedding_model` |
| `entity_extraction.py` | Nothing — run the real spaCy model | Feed it "Metformin treats type 2 diabetes" from the sample data already in `app/backend/data/raw/`, assert the extracted relationship's verb is `"treat"` — this is the one Tier 2 case worth testing against the *real* model rather than mocking it, since the whole point is verifying the co-occurrence heuristic behaves sensibly on realistic input |

`requirements-dev.txt` already has `moto` and `fakeredis` staged for this tier — added now, unused until Tier 2 lands.

## 5. Tier 3 — planned, blocked on infrastructure

`tests/test_api.py` using FastAPI's `TestClient` against real `/upload` and `/ask`. Deliberately not started yet: it needs either live AWS+Postgres+OpenSearch+Redis, or `docker-compose` with `moto`/localstack standing in for AWS — and `docker-compose.yml` currently has no `Dockerfile` to build against (a gap flagged earlier in this project). No point building integration tests against infrastructure that doesn't run yet.

---

## 6. How to run what exists

```bash
pip install -r requirements-dev.txt   # adds pytest, moto, fakeredis on top of requirements.txt
python -m spacy download en_core_web_sm

pytest                                  # runs everything under tests/, per pytest.ini
pytest tests/utils tests/evaluation tests/prompts tests/schemas   # Tier 1 subset that needs the least installed
```

`pytest.ini` sets `pythonpath = .` so `from app.backend...` and `from evaluation...` imports resolve regardless of where `pytest` is invoked from, and scopes discovery to `testpaths = tests`.
