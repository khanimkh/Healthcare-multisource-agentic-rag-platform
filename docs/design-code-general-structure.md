> **Reading guide**: Sections 1–3 below (`bedrock_service.py`, `settings.py`, `router.py`) and the `main.py` section are **generic architectural templates** — the class/field/import names (`AIService`, `cache_url`, `app.schemas...`, `StorageService`) are illustrative placeholders, not this project's real names. They teach a *pattern*, not this codebase specifically. The "AI service layering" section further down, and the pipeline example right before it, **are** meant to describe this project's actual code — the pipeline example had drifted out of date and has been corrected below; the AI service layering section has been fixed to match a diagram error that also existed in `docs/model-service.md` (already fixed there).

---------------------------------
# 1. General template coding for a service file: bedrock_service.py

## Purpose
For production AI systems, a service file that communicates with an external API (AWS Bedrock, Azure OpenAI, OpenAI, Vertex AI, etc.) usually follows a consistent structure. The idea is to initialize the client once, then provide one or more methods that perform specific tasks.

## General Structure

A general template looks like this:

import json
from external_sdk import Client
from app.config.settings import settings


class AIService:
    def __init__(self):
        """
        Initialize the client once.
        This runs when the service object is created.
        """
        self.client = Client(
            endpoint=settings.endpoint,
            api_key=settings.api_key
        )

    def task_name(self, input_data):
        """
        Perform one AI task.
        """

        # 1. Build prompt (optional)
        prompt = f"""
        Your instructions...

        Input:
        {input_data}
        """

        # 2. Build request body
        body = {
            ...
        }

        # 3. Send request
        response = self.client.some_api_method(
            ...
        )

        # 4. Parse response
        result = ...

        # 5. Return processed result
        return result

## Flow

Every AI service function usually follows these five steps:

Input
   │
   ▼
1. Prompt Construction
   │
   ▼
2. Request Body
   │
   ▼
3. API Request
   │
   ▼
4. Parse Response
   │
   ▼
5. Return Result

------------------------

# 2. Configuration File (`settings.py`)

## Purpose

The configuration file centralizes all application settings so you don't hardcode values throughout your project. It loads environment variables from a `.env` file and provides them as a single `settings` object.

---

## General Structure

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
     # ========= Cloud Configuration =========
     cloud_region: str
     api_key: str
     endpoint: str

     # ========= Database =========
     database_url: str

     # ========= Storage =========
     storage_bucket: str

     # ========= AI Models =========
     llm_model: str
     embedding_model: str

     # ========= Cache =========
     cache_url: str

     # ========= Other Configuration =========
     default_index: str

     class Config:
          env_file = ".env"


settings = Settings()
```

---

## Typical Sections

```text
Settings
│
├── Cloud
├── AI Models
├── Database
├── Storage
├── Cache
├── Security
├── Logging
└── Environment Variables
```

---

## Flow

```text
.env
    │
    ▼
Settings(BaseSettings)
    │
    ▼
settings object
    │
    ▼
Used everywhere
```
------------------------------
# 3. `router.py`

For production **FastAPI** applications (AI, RAG, ML, Agentic AI, etc.), the `router.py` file is **the orchestration layer**. It should **coordinate** the workflow by calling tools, services, and agents, not implement their internal logic.

A good mental model is:

> **Router = Traffic Controller**
>
> It receives the request, calls the right components, and returns the response.

---

## General Structure of `router.py`

```python
# ===============================
# 1. Imports
# ===============================

# Standard Python libraries
import ...

# FastAPI
from fastapi import ...

# Schemas
from app.schemas... import ...

# Tools
from app.tools... import ...

# Services
from app.services... import ...

# Agents
from app.agents... import ...

# Config
from app.config.settings import settings

# ===============================
# 2. Router
# ===============================
router = APIRouter()

# ===============================
# 3. Constants
# ===============================
UPLOAD_DIR = ...

# ===============================
# 4. API Endpoint
# ===============================
@router.post(...)
async def endpoint(...):
    try:
      # Step 1
      # Receive request

      # Step 2
      # Validate request

      # Step 3
      # Initialize services/agents

      # Step 4
      # Load data

      # Step 5
      # Clean / preprocess data

      # Step 6
      # Run AI agents

      # Step 7
      # Store results

      # Step 8
      # Cache metadata

      # Step 9
      # Return response
      ...
    except Exception:
      raise HTTPException(...)
```

---

## Typical Workflow

Almost every AI endpoint follows this pipeline:

```text
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
```

---

## Typical Responsibilities

### Step 1 - Receive Request

The router receives:

```python
async def upload(file: UploadFile):
```

or:

```python
async def ask(request: QueryRequest):
```

The router **never processes the file itself**.

---

### Step 2 - Validate

Example:

```python
if file_type == "unknown":
    raise HTTPException(...)
```

Purpose:

- validate input
- reject invalid requests

---

### Step 3 - Initialize Components

Usually instantiate the objects needed for this request.

```python
storage = StorageService()
classifier = ClassificationAgent()
cache = CacheService()
database = DatabaseService()
```

Notice:

The router does **not know how** these components work.

It simply calls them.

---

### Step 4 - Load Data

Usually from **tools**.

Example:

```python
loaded_data = load_data(path)
```

or:

```python
image = load_image(...)
```

or:

```python
pdf = load_pdf(...)
```

---

### Step 5 - Clean / Preprocess

Usually from **tools**.

Example:

```python
clean_data(...)
```

```python
clean_text(...)
```

```python
normalize(...)
```

```python
chunk_documents(...)
```

The router **doesn't implement preprocessing**.

---

### Step 6 - Call AI Agents

Usually from **agents**.

Example:

```python
classifier.classify(...)
```

```python
sql_agent.generate_query(...)
```

```python
planner.plan(...)
```

```python
retriever.retrieve(...)
```

```python
summarizer.generate(...)
```

Notice:

AI logic belongs inside the agent.

---

### Step 7 - Store Results

Usually via services.

Example:

```python
database.save(...)
```

```python
storage.upload(...)
```

```python
vector_store.index(...)
```

---

### Step 8 - Cache

Example:

```python
cache.set(...)
```

Used to speed up future requests.

---

### Step 9 - Return Schema

Finally:

```python
return ResponseSchema(...)
```

Never:

```python
return {
    ...
}
```

Use Pydantic schemas.

-----------------------------------------------

# main.py file

This file is usually called **`main.py`** and serves as the **entry point** of a FastAPI application. It is responsible for creating the FastAPI app, configuring middleware, registering routers, and defining basic endpoints such as health checks. It should **not** contain business logic, AI logic, or database operations.

---

# General Structure of `main.py`

```python
# ======================================
# 1. Imports
# ======================================
from fastapi import FastAPI
from fastapi.middleware...
from app.api.router import router
from app.config.settings import settings

# ======================================
# 2. Create FastAPI Application
# ======================================
app = FastAPI(
    title="...",
    version="...",
    description="...",
)

# ======================================
# 3. Configure Middleware
# ======================================
app.add_middleware(
    MiddlewareClass,
    configuration...
)

# ======================================
# 4. Register API Routers
# ======================================
app.include_router(router)
app.include_router(...)
app.include_router(...)

# ======================================
# 5. Global Endpoints
# ======================================
@app.get("/")
def root():
    ...


@app.get("/health")
def health():
    ...

# ======================================
# 6. Startup / Shutdown Events (Optional)
# ======================================
@app.on_event("startup")
async def startup():
    ...


@app.on_event("shutdown")
async def shutdown():
    ...
```

---

# General Workflow

```text
Application Starts
        │
        ▼
Create FastAPI App
        │
        ▼
Load Configuration
        │
        ▼
Configure Middleware
        │
        ▼
Register Routers
        │
        ▼
Register Global Endpoints
        │
        ▼
Application Ready
```
-----------------------------------

# aws-storage file

## dictionary:

## Example from an AWS/OpenSearch project

Suppose your search function returns search results:

```python
results: List[Dict[str, Any]] = [
    {
        "document_id": "doc1",
        "text": "Patient has diabetes.",
        "score": 0.92,
        "metadata": {
            "source": "ehr.pdf"
        }
    },
    {
        "document_id": "doc2",
        "text": "Blood pressure is normal.",
        "score": 0.85,
        "metadata": {
            "source": "lab.csv"
        }
    }
]
```

Here:

- `results` is a **list**.
- Each item is a **dictionary**.
- The keys (`"document_id"`, `"text"`, `"score"`, `"metadata"`) are all **strings**.
- The values can be **strings**, **floats**, or even **another dictionary**, which is why the value type is `Any`.

---

### Visual representation

```python
results = [
    {
        "id": 1,
        "text": "Hello",
        "score": 0.95
    },
    {
        "id": 2,
        "text": "World",
        "score": 0.88
    }
]
```

```text
List
│
├── Dictionary
│     ├── Key: "id"    -> Value: 1
│     ├── Key: "text"  -> Value: "Hello"
│     └── Key: "score" -> Value: 0.95
│
└── Dictionary
      ├── Key: "id"    -> Value: 2
      ├── Key: "text"  -> Value: "World"
      └── Key: "score" -> Value: 0.88
```

So, **`List[Dict[str, Any]]` means "a list of dictionaries where every key is a string and every value can be of any type."**

-------------------------------

## Upload original file, read document, classify docs, extract graph facts, chunk and embed, bulk index

> **Corrected**: the previous version of this example imported `app.backend.services.aws_storage` (real path: `services/aws_storage_service.py`), `app.backend.services.bedrock_service` (removed entirely), `app.backend.utils.document_loader` and `app.backend.utils.chunking` (neither exists — the real module is `tools/`, not `utils/`), and called `bedrock.classify_text()`/`bedrock.create_embedding()` on a class that no longer exists. It also omitted the entity/relationship extraction step entirely. This is `DocumentIngestionWorkflow.ingest()`'s real logic (see `docs/workflows.md` for the full field-by-field breakdown), not a hypothetical:

```python
from app.backend.agents.classification_agent import ClassificationAgent
from app.backend.services.aws_storage_service import AWSStorage, OpenSearchVectorStore
from app.backend.services.graph_store_service import GraphStoreService
from app.backend.tools.data_loader import load_document
from app.backend.tools.entity_extraction import extract_entities_and_relationships
from app.backend.tools.rag_utils import chunk_documents, create_embeddings_for_chunks


def ingest_uploaded_document(file_path: str, file_name: str):
    """
    Full ingestion pipeline for a document (PDF/DOCX/TXT/image):
    1. Upload original file to S3
    2. Extract text
    3. Classify document type
    4. Extract entities/relationships into the knowledge graph
    5. Split text into chunks
    6. Create embeddings
    7. Bulk-index chunks + vectors into OpenSearch
    """

    # Initialize services/agents
    storage = AWSStorage()
    classification_agent = ClassificationAgent()
    graph_store = GraphStoreService()
    vector_store = OpenSearchVectorStore()

    # Step 1: Upload original file to S3
    upload_result = storage.upload_file_to_s3(file_path=file_path, file_name=file_name)
    file_id, s3_uri = upload_result["file_id"], upload_result["s3_uri"]

    # Step 2: Extract text — dispatches to load_pdf/load_docx/load_txt/load_image_ocr by extension
    text = load_document(file_path)

    # Step 3: Classify document type — via ClassificationAgent -> LLMService, not a removed BedrockService
    document_type = classification_agent.classify_document(text)

    # Step 4: Extract entities/relationships (spaCy) and upsert into the knowledge graph
    extraction = extract_entities_and_relationships(text)
    for relationship in extraction["relationships"]:
        graph_store.upsert_edge(
            source_name=relationship["source"], target_name=relationship["target"],
            relationship=relationship["relationship"], file_id=file_id,
            evidence=relationship["evidence"]
        )

    # Step 5: Split text into chunks (default chunk_size=1000, chunk_overlap=150)
    text_chunks = chunk_documents(text)

    # Step 6: Create one embedding per chunk (via EmbeddingService, not a manual bedrock.create_embedding loop)
    embedded_chunks = create_embeddings_for_chunks(text_chunks)

    # Step 7: Bulk-index into OpenSearch — auto-creates the index on first call
    vector_store.index_chunks(
        chunks=embedded_chunks, file_id=file_id, file_name=file_name,
        document_type=document_type, s3_uri=s3_uri,
        metadata={"source": "user_upload"}, batch_size=500
    )

    return {
        "status": "indexed",
        "file_id": file_id,
        "file_name": file_name,
        "document_type": document_type,
        "s3_uri": s3_uri,
        "chunks_indexed": len(embedded_chunks),
        "entities_extracted": len(extraction["entities"]),
        "relationships_extracted": len(extraction["relationships"])
    }
```

Example call:

```python
result = ingest_uploaded_document(
    file_path="data/clinical_guideline.pdf",
    file_name="clinical_guideline.pdf"
)

print(result)
```

The flow is:

```text
Document/image
-> upload to S3
-> extract text
-> classify document type
-> extract entities/relationships -> upsert into knowledge graph
-> split into chunks
-> create embedding per chunk
-> create OpenSearch index if it does not exist
-> bulk save all chunks into OpenSearch
```

Inside this line:

```python
vector_store.index_chunks(...)
```

your function automatically calls:

```python
self.create_index_if_not_exists(dimension=dimension)
```

So you do not need to call `create_index_if_not_exists()` manually outside.

------------------------------------

# AI service layering: model_service.py, embedding_service.py, llm_service.py, memory_service.py

## Purpose

As a project grows, a single service file that both talks to the raw API **and** implements task-specific logic becomes hard to reuse. The fix is to split the "AI service" into layers, each with **one job**, so higher layers can be swapped or reused without touching the raw client code.

> **Rule of thumb:** only one file in the whole project should ever create the raw client (`boto3.client("bedrock-runtime")`). Everything else calls that file instead of calling AWS directly.

---

## The layers

> **Corrected**: the diagram below used to draw `ClassificationAgent` feeding directly into `ModelService`, parallel to `LLMService`. That doesn't match the real code — `ClassificationAgent.__init__` does `self.llm_service = LLMService()`, exactly like every other agent. It was a genuine diagram/prose mismatch: the "In plain words" section right below already described it correctly. Fixed here, and the same fix was already made in `docs/model-service.md`. The "Agents" box also only listed 6 of the 9 real agents (`graph_rag`, `classification`, and `chart` — the newest one — were missing); all 9 are listed now.

```text
Ingestion (rag_utils.py,                    Agents that reason (router, rag, sql, s3,
document_ingestion_workflow.py,             chart, classification, summarization,
structured_ingestion_workflow.py)           final_answer, graph_rag) — 9 total
        │                                          │
        ▼                                          ▼
  EmbeddingService                          LLMService          <- text generation only
        │                                          │                 (generate, generate_with_history)
        │                                          │
        │              ClassificationAgent ────────┤  (just another LLMService consumer,
        │              (classify_document,          │   not a separate direct-to-ModelService path)
        │               classify_structured_data)   │
        │                                            │
        ▼                                            ▼
              ModelService  ◄─────────────────────────
                    │
                    ▼
            Amazon Bedrock Runtime
```

In plain words:

```text
ModelService         = the ONLY file that owns the boto3 bedrock-runtime client.
                       Exposes two generic primitives:
                       invoke_text_model(prompt, ...)
                       invoke_embedding_model(text)

EmbeddingService      = single source of truth for "turn text into a vector".
                       Composes ModelService. Used by ingestion (chunk embeddings)
                       and by retrieval (embedding the user's question in RAGAgent).

LLMService            = single source of truth for "turn a prompt into an answer".
                       Composes ModelService. Used by all 9 agents that reason/
                       generate text: router, rag, sql, s3, chart, summarization,
                       classification, final_answer, graph_rag. `chart_agent.py`
                       is the newest addition, powering the Insights tab's chart
                       explorer — it is NOT part of question_graph.py's routing.

ClassificationAgent    = classifies uploaded content into a category, via LLMService +
                       prompts/classification_prompt.py. Used by both ingestion
                       workflows (documents and structured datasets) and reused by
                       question_graph.py's "classification" route.

MemoryService         = conversation/session history. Not part of the Bedrock chain -
                       it stores turns in Postgres (durable) and caches the most
                       recent turns in Redis via CacheService (fast lookups), so
                       LLMService.generate_with_history() has something to read from.
```

`services/bedrock_service.py` used to sit here as a task-specific wrapper (`classify_text`, `create_embedding`) between the agents/workflows and `ModelService`. It was removed once both responsibilities had a proper home elsewhere: classification moved to `ClassificationAgent` (which builds its prompt via `prompts/classification_prompt.py` and reasons through `LLMService`, consistent with every other agent), and embedding moved to calling `EmbeddingService` directly. Keeping `BedrockService` around afterward would have meant an empty passthrough class with no distinct responsibility — the same anti-pattern this layering exists to avoid.

---

## Why split `ModelService` from everything above it?

If prompt-building and raw `invoke_model` boilerplate live in the same class, every new task (classification, SQL generation, summarization, routing) either duplicates that boilerplate or gets crammed into one class named after a single task. Splitting them means the raw call (`invoke_model`, `json.dumps`, `contentType`, response parsing) lives in exactly one place, and every higher-level file only decides **what prompt** to send and **how to shape the result**.

---

## Responsibility table

| File | Owns raw client? | Responsibility | Used by |
| --- | --- | --- | --- |
| `model_service.py` | ✅ Yes | Generic `invoke_text_model` / `invoke_embedding_model` calls to Bedrock Runtime | `embedding_service.py`, `llm_service.py` |
| `embedding_service.py` | No | Turn text into a vector (single chunk or batch) | `rag_utils.py` (ingestion), `rag_agent.py` (retrieval) |
| `llm_service.py` | No | Turn a prompt (optionally with conversation history) into a generated answer | All 9 agents: router, rag, sql, s3, chart, graph_rag, summarization, classification, final_answer |
| `agents/classification_agent.py` | No | Classify a document's text or a structured dataset's columns into a category | `document_ingestion_workflow.py`, `structured_ingestion_workflow.py`, `question_graph.py` |
| `agents/chart_agent.py` | No | Generate/execute aggregation SQL for the chart explorer, propose chart-worthy questions | `visualization_workflow.py` (separate from `question_graph.py` — see `docs/question-graph-agents-prompts.md` §4) |
| `memory_service.py` | N/A (Postgres + Redis, not Bedrock) | Store/retrieve conversation turns per session | `question_graph.py`, `question_workflow.py` |

---

## Flow

```text
Raw model call
   │
   ▼
ModelService.invoke_text_model() / invoke_embedding_model()
   │
   ├──► EmbeddingService.create_embedding()   -> used at ingestion + retrieval time
   │
   └──► LLMService.generate()  ◄──────────────── ClassificationAgent builds a prompt via
            │                                    prompts/classification_prompt.py and calls
            ▼                                    this, same as every other agent
        Agents build task prompts and call LLMService
```

`LLMService.generate_with_history()` exists (builds a prompt from a conversation history plus a new question, then delegates to `generate()`) but — verified by checking for callers — **has none** as of this writing. The actual conversation-memory path is different: `QuestionWorkflow` reads recent turns via `MemoryService.get_recent_messages()` and threads them into `state["conversation_context"]`, which only `RouterAgent.route()` ever reads (see `docs/question-graph-agents-prompts.md` §7 and `docs/bedrock-service.md`). `generate_with_history()` is a ready-to-use alternative, not part of the active call path — don't assume it's wired in just because it exists.

------------------------------------

