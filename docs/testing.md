# Guide: testing this project

`tests/` was empty until this pass. This doc explains the three-tier plan, what's actually implemented (Tier 1) versus planned (Tier 2/3), how to run what exists, and a couple of real findings the process surfaced.

---

## 1. Why three tiers, not one flat `tests/` folder

This project's core value is orchestrating external systems — Bedrock, S3, OpenSearch, Postgres, Redis, Glue, Athena. Almost nothing here is testable in true isolation the way a pure algorithm library would be. Rather than write brittle tests that either (a) secretly require live AWS credentials to pass, or (b) mock everything so heavily they stop testing real behavior, the tests are organized by *how much mocking they need*, and each tier is written differently on purpose:

```text
Tier 1  ->  pure logic, no mocking, no live services       (this pass)
Tier 2  ->  mocked AWS/Redis, or SQLite standing in for Postgres   (next)
Tier 3  ->  real FastAPI TestClient against /upload and /ask       (later — infrastructure exists now, just not started)
```

---

## 2. Tier 1 — implemented this pass

```text
tests/
├── utils/test_validators.py             (12 tests)
├── evaluation/test_metrics.py           (11 tests)
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
| `test_summarization_agent.py` | `resolve_document()`'s word-overlap scoring against real sample filenames (`readmission_risk_guideline.txt`, `lab_result_thresholds.txt`, etc. — the same files generated for manual testing) | Updated since first written — see the note below |
| `test_schemas.py` | Required-field enforcement and defaults for `QuestionRequest`/`QuestionResponse`/`UploadResponse`, including that both ingestion workflows' actual return shapes validate correctly | Pydantic-only, no app imports needed |

**Update**: `test_summarization_agent.py` originally called a private `SummarizationAgent._resolve_document()` method via the `__new__` constructor-bypass trick described below. That method was later extracted into `tools/document_resolution.resolve_document()` — a plain, dependency-free function shared with `ClassificationAgent` (see `docs/question-graph-agents-prompts.md` §4) — but the test file wasn't updated at the same time, so it silently broke: it called a method that no longer existed on the class. Fixed now: the test imports `resolve_document()` directly and no longer needs `SummarizationAgent.__new__()` at all, since the function it's testing has zero AWS dependencies. This is exactly the outcome Finding 2 (below) predicted would be an improvement — it happened, just not in the same pass that wrote the original test.

### What was actually verified, honestly

`pytest` itself still isn't installed in this dev environment (same limitation flagged throughout this project's build — verified again just now: `python -m pytest --version` → `No module named pytest`). So instead of just writing files and asserting they'd pass, every test function in `test_validators.py`, `test_metrics.py`, and all seven `test_*_prompt.py` files was executed directly as a plain Python function (they only use `assert`, no pytest-specific features) — **50 test functions, 0 failures**, for real. `test_schemas.py`'s logic was verified the same way, substituting `pytest.raises` with `try/except` for the manual run — **6 for 6**. `test_summarization_agent.py`'s 4 tests were re-verified after the `resolve_document()` fix above, run directly as plain functions — **4 for 4**, and since the fixed version imports only `tools/document_resolution.py` (no `boto3`/`opensearchpy` in its import chain), it's now one of the tests that needs the *least* installed to run, not one that's blocked.

`test_data_loader.py` still could **not** be executed here — see below.

---

## 3. Real findings from actually trying to run these

### Finding 1: heavy module-level imports block testing lightweight functions

`detect_file_type()` in `tools/data_loader.py` is pure, dependency-free logic (just `os.path.splitext`). But the *module* it lives in does `from pypdf import PdfReader`, `from docx import Document`, `from PIL import Image`, `import pytesseract` at the top — unconditionally, even though `detect_file_type()` never calls any of them. Importing the module to test one trivial function requires all four of those packages installed. This is why `test_data_loader.py` couldn't run in this sandbox even though the function it tests has zero real dependencies.

Not fixed here — fixing it would mean making those imports lazy (moved inside the functions that actually use them), which is a real behavior-neutral improvement worth doing, but a separate change from writing the test.

### Finding 2 (resolved): pure logic trapped behind a heavy constructor

`SummarizationAgent._resolve_document()` didn't touch `self` at all — it was pure string-matching logic, but calling it required constructing a `SummarizationAgent()` first, whose `__init__` built an `LLMService` and `OpenSearchVectorStore` needing `boto3`/`opensearchpy` importable. The original test worked around this with `SummarizationAgent.__new__(SummarizationAgent)`. This was flagged as "a signal: a class where a 'bypass the constructor' trick is needed to test one pure method is a class that could benefit from separating pure logic out from AWS-dependent setup" — and that's exactly what happened next: the logic was extracted into `tools/document_resolution.resolve_document()`, a standalone function with no class, no constructor, no AWS dependency at all. The lesson generalizes: when a "test needs a constructor-bypass trick" finding shows up, treat it as a refactor signal, not just a testing footnote — and remember to update the test when the refactor happens, since this one didn't get updated until this pass caught it broken.

### Finding 3: a coverage gap on everything added after this pass

Nothing written in Tier 1 covers code added to the project after this testing pass: `agents/chart_agent.py`, `services/schema_service.py`, `utils/sql_cleanup.py`, `workflows/visualization_workflow.py`, or the `/visualizations` endpoints. All of these are exercised by manual `curl`/Docker verification (see the session's own history) but have zero automated test coverage. `clean_sql_response()` in particular (`utils/sql_cleanup.py`) is a small, pure, dependency-free string function — exactly the shape Tier 1 targets — and would be a natural next addition: it fixed a real bug (a stray `sql\n` markdown-fence prefix breaking the read-only-SQL check) that a regression test could have caught automatically instead of via manual `curl` testing.

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

## 5. Tier 3 — planned, no longer blocked on infrastructure

`tests/test_api.py` using FastAPI's `TestClient` against real `/upload` and `/ask`. This was originally blocked on `docker-compose.yml` having no `Dockerfile` to build against — that gap is closed (`Dockerfile` exists, `docker compose up -d --build` runs the full 3-container stack — `backend`, `postgres`, `redis` — successfully, verified repeatedly throughout this project's build). The remaining blocker is different now: Tier 3 as originally scoped needs either live AWS credentials (Bedrock/S3/OpenSearch/Glue/Athena) reachable from wherever tests run, or `moto`/localstack standing in for all of them, neither of which is set up yet. Simply not started, not infrastructure-blocked.

---

## 6. How to run what exists

```bash
pip install -r requirements-dev.txt   # adds pytest, moto, fakeredis on top of requirements.txt
python -m spacy download en_core_web_sm

pytest                                  # runs everything under tests/, per pytest.ini
pytest tests/utils tests/evaluation tests/prompts tests/schemas tests/agents   # Tier 1 subset that needs the least installed
```

`pytest.ini` sets `pythonpath = .` so `from app.backend...` and `from evaluation...` imports resolve regardless of where `pytest` is invoked from, and scopes discovery to `testpaths = tests`.
