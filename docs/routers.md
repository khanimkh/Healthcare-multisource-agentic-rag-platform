# Guide: `api/routes.py`

> Full rewrite. The previous version of this doc documented a much older `api/routes.py` that inlined the whole upload pipeline directly in the route handler (calling `tools.aws_storage`, `tools.database.RDSStorage`, `glue_catalog.register_metadata()`, `clean_dataframe()`/`clean_text()` directly) and only had one endpoint, `/upload`. None of that exists anymore — every deleted function/class it described (`RDSStorage`, `glue_catalog.register_metadata()`, `clean_dataframe()`, `clean_text()`, `load_data()`) is confirmed gone from the codebase. The router today is a thin orchestration layer with six real endpoints, each delegating to a workflow class. See `docs/load-data.md`, `docs/rag-utils.md`, `docs/aws-storage.md`, `docs/RDS-glue.md`, and `docs/question-graph-agents-prompts.md` for what each workflow actually does internally — this doc only covers the HTTP layer.

---

# 1. What lives here vs. `main.py`

```text
main.py
────────────────────────
FastAPI app, CORS middleware
GET  /        -> serves static/index.html (the frontend)
GET  /health  -> {"status": "healthy"}
app.include_router(router)  -> mounts everything below
────────────────────────

api/routes.py
────────────────────────
POST   /upload
GET    /documents
DELETE /documents/{file_id}
POST   /ask
GET    /visualizations/suggestions
POST   /visualizations
────────────────────────
```

`/` and `/health` are simple enough that they live directly in `main.py` rather than `routes.py` — no workflow, no business logic, nothing worth a separate router for.

---

# 2. Module-level singletons

```python
document_ingestion_workflow = DocumentIngestionWorkflow()
structured_ingestion_workflow = StructuredIngestionWorkflow()
question_workflow = QuestionWorkflow()
visualization_workflow = VisualizationWorkflow()
document_store = DocumentStore()
```

Same pattern as `question_graph.py`'s agent singletons (`docs/question-graph-agents-prompts.md` §3): constructed once at import time, shared across every request, not recreated per-request. Every route handler below just calls a method on one of these five objects — no route handler constructs a workflow or service itself.

---

# 3. Endpoints, one by one

## `POST /upload` → `UploadResponse`

```python
async def upload_file(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{original_file_name}")

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_type = detect_file_type(local_path)

    if file_type == "unknown":
        os.remove(local_path)
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        if file_type == "structured":
            result = structured_ingestion_workflow.ingest(file_path=local_path, file_name=original_file_name)
        else:
            result = document_ingestion_workflow.ingest(file_path=local_path, file_name=original_file_name)

        return UploadResponse(file_type=file_type, **result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
```

Step by step:

1. **Save locally first** — every upload is written to `app/backend/data/raw/{uuid}_{original_name}` before anything else happens. The `uuid` prefix (not the same UUID as the eventual `file_id` — this one's discarded, `DocumentIngestionWorkflow`/`StructuredIngestionWorkflow` each generate their own `file_id` internally) exists purely to avoid local filename collisions between concurrent uploads of files with the same name.
2. **`detect_file_type()`** (`tools/data_loader.py`, see `docs/load-data.md`) decides `"structured"` / `"document"` / `"image"` / `"unknown"`. Only `"unknown"` is rejected here with a 400; everything else proceeds.
3. **Branch to exactly one workflow** — `"structured"` goes to `StructuredIngestionWorkflow.ingest()` (CSV → Glue + Postgres dual-write, `docs/RDS-glue.md`); anything else goes to `DocumentIngestionWorkflow.ingest()` (text extraction → classification → entity extraction → chunk/embed → OpenSearch, `docs/rag-utils.md` + `docs/question-graph-agents-prompts.md`). Note `"image"` also goes to the document workflow, not a separate path — see the routing-branch nuance documented in `docs/load-data.md`.
4. **`UploadResponse(file_type=file_type, **result)`** — the workflow's return dict is spread into the response model; `file_type` is added here because the workflows themselves don't know (or need to know) which branch dispatched them.
5. **`finally: os.remove(local_path)`** — the local temp copy is deleted whether ingestion succeeded or raised. Nothing in this pipeline keeps a permanent local copy; the durable copy is the one `AWSStorage.upload_file_to_s3()` writes to S3, inside the workflow.
6. **Any exception during ingestion becomes a 500** with the raw exception message as `detail` — there's no partial-success response; either the whole workflow completes or the client gets an error (though the workflow itself still marks the document `"failed"` in Postgres before re-raising, so the failure is visible in `GET /documents` too).

## `GET /documents` → `List[DocumentRecordResponse]`

```python
async def list_documents():
    return document_store.list_all_documents()
```

The thinnest endpoint in the file — a direct passthrough to `DocumentStore.list_all_documents()` (`docs/RDS-glue.md`), ordered newest-first. This is what the Upload tab's document list renders. It's unrelated to the Insights tab's chart suggestions below — those come from `SchemaService` introspecting Postgres table *schemas* directly via SQLAlchemy, not from the `documents` metadata table at all (which is explicitly excluded from that introspection via `INTERNAL_TABLES`, see `docs/question-graph-agents-prompts.md` §7).

## `DELETE /documents/{file_id}`

```python
async def delete_document(file_id: str):
    document = document_store.get_document(file_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    document_ingestion_workflow.vector_store.delete_chunks(file_id)
    document_ingestion_workflow.storage.delete_file(document["s3_uri"])
    document_store.delete_document(file_id)

    return {"status": "deleted", "file_id": file_id, "note": "..."}
```

Three cleanup calls, in order: OpenSearch chunks, the S3 object, then the Postgres `documents` row. Notice this always reuses `document_ingestion_workflow.vector_store`/`.storage` — even when deleting a structured (CSV) upload, whose file was actually uploaded via `structured_ingestion_workflow`'s own separate `AWSStorage` instance. This works because `AWSStorage`/`OpenSearchVectorStore` are stateless clients scoped to the same S3 bucket / OpenSearch index regardless of which workflow constructed them, not because there's only one instance — there are two separate `AWSStorage()` instances (one per ingestion workflow), and this endpoint happens to always use `document_ingestion_workflow`'s one rather than picking the workflow that actually created the file.

**What this does NOT clean up**, and the response's own `note` field says so explicitly: the Glue table and any knowledge-graph (`graph_nodes`/`graph_edges`) entries created from this document. It also silently doesn't clean up the Postgres dual-write table (e.g. `test_patients`) for a deleted CSV upload — not even mentioned in the `note`, a gap documented in `docs/RDS-glue.md`. Deleting a document today means its data may still be fully queryable via `sql`/`s3` after the fact, even though it's gone from the document list, RAG, and classification/summarization resolution.

## `POST /ask` → `QuestionResponse`

```python
async def ask_question(request: QuestionRequest):
    result = question_workflow.ask(question=request.question, session_id=request.session_id)
    return QuestionResponse(**result)
```

The entire question-answering system (routing, all six tool agents, final answer composition, conversation memory) lives behind this one call to `QuestionWorkflow.ask()` — see `docs/question-graph-agents-prompts.md` for everything that happens inside it. This endpoint itself does nothing but pass the request through and wrap exceptions.

## `GET /visualizations/suggestions` → `ChartSuggestionsResponse`

```python
async def get_chart_suggestions():
    questions = visualization_workflow.suggest()
    return ChartSuggestionsResponse(questions=questions)
```

Powers the Insights tab's suggestion dropdown — introspects the current Postgres schema and asks an LLM to propose meaningful chart questions. Not part of the `/ask` routing graph at all (see the scope note in `docs/question-graph-agents-prompts.md` §4); this is `ChartAgent`/`VisualizationWorkflow`'s own endpoint.

## `POST /visualizations` → `ChartResponse`

```python
async def generate_chart(request: ChartRequest):
    result = visualization_workflow.chart(question=request.question)
    return ChartResponse(**result)
```

Takes a natural-language chart question (typed or picked from the suggestions dropdown), generates and runs an aggregation SQL query, and returns `{title, sql, labels, values}` ready for the frontend's bar/pie/line chart renderer. This is the only endpoint that catches `ValueError` separately and maps it to a 400 rather than a 500 — `SQLAgent.execute()` (which `ChartAgent.build_chart()` calls into) raises `ValueError` specifically when the generated SQL fails the read-only safety check, which is a client-triggerable "the model didn't produce a safe query" situation, not an unexpected server error.

---

# 4. Shared FastAPI/Python building blocks

These concepts recur across every endpoint above and are worth naming once rather than per-endpoint:

| Concept | What it does here |
| --- | --- |
| `APIRouter()` | Groups all six endpoints so `main.py` can mount them in one `app.include_router(router)` call instead of registering each individually |
| `response_model=...` | Every endpoint except `DELETE /documents/{file_id}` declares a Pydantic response model (`UploadResponse`, `List[DocumentRecordResponse]`, `QuestionResponse`, `ChartSuggestionsResponse`, `ChartResponse`) — FastAPI validates the return value against it and generates the OpenAPI schema from it. The delete endpoint returns a plain dict instead, since its shape is a small fixed `{status, file_id, note}` not worth a dedicated schema |
| `UploadFile = File(...)` | Only `/upload` needs this — it's what makes FastAPI parse the request as `multipart/form-data` instead of JSON |
| `HTTPException(status_code=..., detail=...)` | The only way any endpoint communicates failure to the client — every endpoint wraps its workflow call in `try/except Exception` and re-raises as a 500 (or a 400, for `/visualizations`'s `ValueError` case, or a 404, for deleting a document that doesn't exist) |
| `logger.error(...)` before re-raising | Every failure is logged server-side with context (the question, the filename, the file_id) before becoming a generic `HTTPException` — the client sees the raw exception message, but the server log additionally has which request caused it |

---

# 5. Why this router is designed this way

This router acts as a thin **HTTP-to-workflow adapter**, nothing more. It doesn't perform OCR, generate embeddings, query Bedrock, run SQL, or talk to OpenSearch/Glue/Athena directly — every one of those responsibilities lives in a workflow, agent, or service class, and the router's only job is: parse the HTTP request, call the right workflow method, shape the result into a response model, and translate exceptions into HTTP status codes.

- **`DocumentIngestionWorkflow` / `StructuredIngestionWorkflow`**: own the entire upload pipeline for their respective file types.
- **`QuestionWorkflow`**: owns the entire question-answering pipeline (routing through six agents).
- **`VisualizationWorkflow`**: owns the chart-explorer pipeline.
- **`DocumentStore`**: owns reading/writing the `documents` Postgres table.

This separation is what let every feature documented elsewhere in `docs/` (reranking, source deduplication, the `SchemaService` extraction, the shared `resolve_document()`) get added without a single line of `routes.py` changing beyond the new endpoint declarations themselves — the router doesn't know or care how a workflow does its job internally.
