> **Outdated, fixed here**: this section described a `BedrockService` class that no longer exists — it had zero "Outdated" warning in earlier versions of this doc, unlike every other doc in this repo that references it, which was worth calling out and fixing directly rather than leaving unmarked. `classify_text()` split into `ClassificationAgent.classify_document()` / `classify_structured_data()` (via `LLMService`); `create_embedding()` moved to `EmbeddingService.create_embedding()` (via `ModelService`). Both are now thin wrappers around a shared `ModelService` that's the *only* file in the project holding a raw Bedrock client — see `docs/bedrock-service.md` for the line-by-line walkthrough and `docs/model-service.md` for the full agent-to-service architecture diagram; not repeated here.

# Classification + embedding, current shape

```text
                User uploads document
                        │
                        ▼
              DocumentIngestionWorkflow
                  /           \
                 /             \
                ▼               ▼
  ClassificationAgent      EmbeddingService
  .classify_document()     .create_embedding()
   (via LLMService)          (via ModelService,
                │              one call per chunk)
                ▼               ▼
     "patient report"     [0.2,-0.1,...]
                │               │
                ├───────────────┤
                        ▼
       OpenSearchVectorStore.index_chunks()
          (bulk-indexed, see docs/aws-storage.md)
                        │
                        ▼
             Semantic search & RAG retrieval
```

The classification result organizes/routes documents (it's what `document_type` becomes in the `documents` table and in each indexed chunk); the embedding is what makes the document retrievable by `RAGAgent` later. Same conceptual shape as the original diagram — classify, embed, store — just through the real current classes.

## Why this design is good

The same reasoning still holds, updated to the real split across `ModelService`/`LLMService`/`EmbeddingService`/`ClassificationAgent` instead of one `BedrockService`:

- **Single Responsibility Principle:** `ModelService` only handles communication with AWS Bedrock; `ClassificationAgent`/`EmbeddingService` only handle "what does my use case need from that."
- **Encapsulation:** No agent needs to know Bedrock's request/response shape — they call `LLMService.generate()` / `EmbeddingService.create_embedding()`.
- **Reusability:** Nine different agents reuse `LLMService` without duplicating request-building code.
- **Maintainability:** Switching models only means changing `ModelService`/`config/settings.py` — every caller stays untouched.
- **Configuration-driven:** Model IDs and AWS region come from `settings`, so different environments don't need code changes.

------------
# routers.py

For production FastAPI applications (AI, RAG, ML, Agentic AI, etc.), the router.py file is the orchestration layer. It should coordinate the workflow by calling tools, services, and agents—not implement their internal logic.

A good mental model is:

Router = Traffic Controller
It receives the request, calls the right components, and returns the response.

Typical Workflow

Almost every AI endpoint follows this pipeline:

HTTP Request
      │
      ▼
Validate Input
      │
      ▼
Load Data
      │
      ▼
Clean / Preprocess
      │
      ▼
Call AI Agent(s)
      │
      ▼
Call External Services
      │
      ▼
Store Results
      │
      ▼
Cache
      │
      ▼
Return Response

## Most important services, current shape

> **Corrected**: the original version of this section claimed every uploaded file goes through both Glue and a Redis cache. Verified against the actual ingestion workflows — that's not what happens. `GlueCatalog` is only used by `StructuredIngestionWorkflow` (CSVs); it never appears in `DocumentIngestionWorkflow`. And `CacheService`/Redis isn't used by either ingestion workflow at all — Redis in this project is used exclusively for conversation memory (`MemoryService`, see `docs/cache_memory_service.md`), not upload metadata.

### Glue Catalog

Registers dataset schema/location metadata for **structured (CSV) uploads only**, so Athena can query them — see `docs/RDS-glue.md`.

### Classification Agent

Uses an LLM to classify **both** documents and structured datasets — `classify_document(text)` and `classify_structured_data(df)` respectively. Example categories: `clinical guideline`, `patient report`, `claims dataset`. See `docs/question-graph-agents-prompts.md`.

### Relational Data Store

Not in the original list, but arguably more load-bearing than a cache service for this pipeline: `RelationalDataStore.load_dataframe()` dual-writes every uploaded CSV into a real Postgres table, which is what makes it queryable via the `sql` route in addition to `s3`/Athena. See `docs/RDS-glue.md`.

## General flow, current shape

```text
             User Upload
                  │
                  ▼
          Save Locally
                  │
                  ▼
             Upload to S3
                  │
                  ▼
           Detect File Type
          ┌────────┴────────┐
          ▼                 ▼
   Structured         Document/Image
   (.csv only)
          │                 │
          ▼                 ▼
   Classify dataset    Classify document
          │                 │
          ▼                 ▼
   Glue + Postgres     Entity/relationship extraction
   (dual-write)        (Postgres graph_nodes/graph_edges)
          │                 │
          │                 ▼
          │            Chunk + embed + OpenSearch
          │                 │
          └────────┬────────┘
                   ▼
          documents table (Postgres)
          status: "registered" / "indexed"
```

No universal Glue step, no universal cache step — each branch's storage footprint is genuinely different, and neither branch touches Redis. Full step-by-step detail (including exact field names in each return value) is in `docs/workflows.md`.
--------------------------

# main.py

---

## Where Middleware Fits

```text
                                                HTTP Request
                                                             │
                                                             ▼
                                                Middleware
                                                             │
                                                             ▼
                                     FastAPI Router
                                                             │
                                                             ▼
                              API Endpoint (/upload)
                                                             │
                                                             ▼
                                     Business Logic
                                                             │
                                                             ▼
                                                HTTP Response
                                                             ▲
                                                             │
                                                Middleware
                                                             │
                                                             ▼
                                                       Client
```

Notice that middleware runs **both before and after** your endpoint.

---

## Why do we need Middleware?

Instead of writing the same code inside every endpoint, middleware performs common tasks **once** for the entire application.

Without middleware:

```python
@app.get("/users")
def get_users():
            authenticate()
            log_request()
            check_cors()
            ...
```

```python
@app.get("/documents")
def get_documents():
            authenticate()
            log_request()
            check_cors()
            ...
```

The same code is repeated everywhere.

With middleware:

```text
Request
      ↓
Authentication
      ↓
Logging
      ↓
CORS
      ↓
Endpoint
```

Every endpoint automatically benefits.

---

## Your Code

```python
app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
)
```

Here you're adding **CORS Middleware**.

---

## What is CORS?

CORS stands for:

**Cross-Origin Resource Sharing**

Browsers normally block requests between different websites.

Example:

```text
Frontend
http://localhost:3000
```

tries to call:

```text
Backend
http://localhost:8000
```

The browser says:

> Different origin.

Without CORS, the browser blocks the request.

---

With CORS middleware:

```text
Browser
      ↓
Checks CORS
      ↓
Allowed?
      ↓
Yes
      ↓
Backend
```
---------------------------