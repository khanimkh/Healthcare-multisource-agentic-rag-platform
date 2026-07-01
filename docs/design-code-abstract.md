# bedrock_service:  
               
                User uploads document
                        │
                        ▼
                BedrockService
                  /           \
                 /             \
                ▼               ▼
      classify_text()    create_embedding()
                │               │
                ▼               ▼
     "patient report"     [0.2,-0.1,...]
                │               │
                ├───────────────┤
                        ▼
            Store in OpenSearch / Vector DB
                        │
                        ▼
             Future semantic search & RAG

The classification result is useful for organizing or routing documents, while the embedding is stored in a vector database (such as OpenSearch) so that future user queries can retrieve semantically similar documents.

## Why this design is good

This class follows several software engineering best practices:

- **Single Responsibility Principle:** It only handles communication with AWS Bedrock.
- **Encapsulation:** The rest of the application doesn't need to know Bedrock API details, request formats, or response parsing.
- **Reusability:** Any part of the application can call `classify_text()` or `create_embedding()` without duplicating code.
- **Maintainability:** If you later switch from Claude to another Bedrock model (or even another provider), you only need to update this service instead of changing code throughout the project.
- **Configuration-driven:** Model IDs and AWS region come from settings, making it easy to use different environments (development, staging, production) without changing the code itself.

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

## 3 most important and new services:

Based on this code, every uploaded file is stored in Amazon S3, and metadata about that file is registered separately (using the Glue Catalog and Redis cache).

### Glue Catalog

Registers dataset metadata.

### Classification Agent

Uses an LLM to classify documents.

Example:

clinical guideline
patient report
claims dataset

### Cache Service

Stores upload metadata in Redis.

## general flow

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
          │                 │
          ▼                 ▼
     PostgreSQL      OpenSearch
          │                 │
          └────────┬────────┘
                   ▼
          Glue Metadata Catalog
                   │
                   ▼
               Redis Cache
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