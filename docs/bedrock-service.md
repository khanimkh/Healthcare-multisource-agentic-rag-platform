> **This doc matches the current code** in `app/backend/services/model_service.py`, `app/backend/services/llm_service.py`, and `app/backend/services/embedding_service.py`. The responsibilities of a BedrockService were split into three layers (see "Where is this used?" below and the "AI service layering" section of `docs/design-code-general-structure.md`).

1. Use an LLM (Claude on Bedrock) to generate text — classification, summarization, SQL generation, RAG answers, reranking, routing, and more.
2. Use an embedding model (Titan Embeddings) to convert text into vectors for semantic search.

Let's go through it section by section.

---

# The three-layer split

Instead of one class that both owns the raw AWS client and knows about every use case, the project splits this into three layers:

```text
Agents (ClassificationAgent, SummarizationAgent, SQLAgent,
        ChartAgent, RAGAgent, RouterAgent, FinalAnswerAgent,
        GraphRAGAgent, S3Agent, ...)
        │
        ▼
LLMService.generate()          EmbeddingService.create_embedding()
        │                               │
        ▼                               ▼
ModelService.invoke_text_model()   ModelService.invoke_embedding_model()
        │                               │
        └───────────────┬───────────────┘
                         ▼
              boto3 bedrock-runtime client
                         │
                         ▼
                    AWS Bedrock
```

- **`ModelService`** is the *only* place in the project that holds a `boto3.client("bedrock-runtime")` and calls `invoke_model(...)` directly — the "single owner of the raw client" principle used throughout this codebase.
- **`LLMService`** and **`EmbeddingService`** are thin, use-case-agnostic wrappers around `ModelService`. Every agent in the project calls one of these two, never `ModelService` directly.
- Agents don't know anything about Bedrock's request/response shape, model IDs, or `boto3` — they just call `self.llm_service.generate(prompt=..., system_prompt=...)` or `self.embedding_service.create_embedding(text)`.

---

# Imports

```python
import json
```

Used to convert Python dictionaries into JSON before sending requests to AWS.

Example:

```python
body = {"inputText": "Hello"}
```

becomes:

```json
{"inputText":"Hello"}
```

using:

```python
json.dumps(body)
```

---

```python
import boto3
```

`boto3` is the official AWS SDK for Python. Here it only communicates with **Bedrock Runtime**, and only inside `ModelService`.

---

```python
from typing import Any, Dict, List, Optional
```

Used for type hints. For example:

```python
def invoke_embedding_model(self, text: str, model_id: Optional[str] = None) -> List[float]:
```

means: this function takes an optional `model_id` override, and always returns a list of floats (the embedding vector).

---

```python
from app.backend.config.settings import settings
```

Imports application configuration instead of hardcoding values. Two settings matter here:

```python
settings.bedrock_llm_model_id   # "us.anthropic.claude-haiku-4-5-20251001-v1:0"
settings.bedrock_embedding_model_id  # "amazon.titan-embed-text-v2:0"
```

Note the `bedrock_llm_model_id` value: the `us.` prefix means it's a cross-region **inference profile ID**, not a raw foundation model ID. Some Bedrock models (like the Claude Haiku model this project uses) can only be invoked through an inference profile, not by calling `invoke_model` with the bare model ID — this project's `settings` already accounts for that.

---

# `ModelService` — owns the raw Bedrock client

```python
class ModelService:
    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
```

Same idea as before: one reusable client created once, reused for every request.

## `invoke_text_model()`

```python
def invoke_text_model(
    self,
    prompt: str,
    system_prompt: Optional[str] = None,
    model_id: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3
) -> str:
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    if system_prompt:
        body["system"] = system_prompt

    response = self.client.invoke_model(
        modelId=model_id or settings.bedrock_llm_model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()
```

This is a **generic** Claude call — not specific to classification like the old `classify_text()` was. Every agent that talks to Claude (classification, summarization, SQL generation, chart SQL generation, RAG answering, reranking, routing) goes through this one function, just with different `prompt`/`system_prompt`/`max_tokens`/`temperature` arguments.

A few details worth calling out:

- **`system_prompt` is optional and conditional.** `body["system"]` is only added if a system prompt was passed in. Every agent in this project *does* pass one (e.g. `RERANK_SYSTEM_PROMPT`, `SQL_SYSTEM_PROMPT`) — it's how each agent tells Claude what role to play, separate from the per-call `prompt`.
- **`max_tokens`/`temperature` are not fixed values.** They default to `1024`/`0.3`, but callers override them per use case — e.g. the router agent uses `max_tokens=20` (it only needs one word back) and `temperature=0` (deterministic routing), while `RAGAgent.answer()` uses `max_tokens=800, temperature=0.2` (longer, slightly varied prose).
- **`model_id` can be overridden per call** via `model_id or settings.bedrock_llm_model_id` — useful if a specific call ever needs a different Claude model, though nothing in this project currently overrides it.
- **Response parsing is unchanged**: `result["content"][0]["text"].strip()` — same Anthropic Messages API response shape as before.

## `invoke_embedding_model()`

```python
def invoke_embedding_model(
    self,
    text: str,
    model_id: Optional[str] = None
) -> List[float]:
    body = {"inputText": text}

    response = self.client.invoke_model(
        modelId=model_id or settings.bedrock_embedding_model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return result["embedding"]
```

Same Titan Embeddings request/response shape as before: `inputText` in, `result["embedding"]` out. The only change from the original design is the `model_id` override parameter, for the same reason as above.

---

# `LLMService` — the wrapper agents actually call

```python
class LLMService:
    def __init__(self):
        self.model_service = ModelService()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        return self.model_service.invoke_text_model(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
```

`generate()` is a direct passthrough to `ModelService.invoke_text_model()` — it exists so agents depend on `LLMService`, not on `ModelService` (and therefore never touch `boto3` or the raw request/response shape at all).

```python
def generate_with_history(
    self,
    question: str,
    history: List[Dict[str, Any]],
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3
) -> str:
```

Builds a single prompt string out of a conversation history plus a new question, then calls `generate()` with it — the general pattern for folding chat history into a stateless `invoke_model` call, since Bedrock's `invoke_model` API has no built-in concept of a multi-turn session. Note: as of this writing, this method has no callers in the codebase — the project's actual session-memory handling threads a `conversation_context` string through `QuestionWorkflow` into the router prompt instead (see `app/backend/workflows/question_workflow.py`), not through this method. It's kept here as a ready-to-use alternative, not dead weight that needs removing, but don't assume it's on the active call path.

---

# `EmbeddingService` — the wrapper for embeddings

```python
class EmbeddingService:
    def __init__(self):
        self.model_service = ModelService()

    def create_embedding(self, text: str) -> List[float]:
        return self.model_service.invoke_embedding_model(text)

    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.create_embedding(text) for text in texts]
```

`create_embedding()` mirrors `LLMService.generate()`: a thin passthrough so callers never see `ModelService` directly. `create_embeddings()` (plural) is a convenience loop over `create_embedding()` — it is **not** a true batch API call; Titan's `invoke_model` only accepts one `inputText` per request, so embedding N texts still means N separate Bedrock calls, just issued from one function.

---

# Where is this used?

```text
                        User uploads document / asks a question
                                        │
              ┌─────────────────────────┴─────────────────────────┐
              ▼                                                     ▼
   Agents that generate text                          Agents/services that embed text
   (ClassificationAgent, SummarizationAgent,           (RAGAgent via EmbeddingService,
    SQLAgent, ChartAgent, RAGAgent,                     DocumentIngestionWorkflow via
    RouterAgent, FinalAnswerAgent, GraphRAGAgent, ...)   EmbeddingService)
              │                                                     │
              ▼                                                     ▼
      LLMService.generate()                          EmbeddingService.create_embedding()
              │                                                     │
              ▼                                                     ▼
  ModelService.invoke_text_model()                 ModelService.invoke_embedding_model()
              │                                                     │
              ▼                                                     ▼
        Claude (via inference profile)                    Titan Embeddings
              │                                                     │
              ▼                                                     ▼
    "clinical guideline", SQL text,                        [0.2, -0.1, ...]
    RAG answers, rerank order, etc.                                 │
                                                                     ▼
                                                     Stored in OpenSearch (bulk-indexed —
                                                     see docs/aws-storage.md) for future
                                                     semantic search & RAG retrieval
```

The **text-generation** side is used for far more than classification now — it powers routing, SQL generation (including the chart explorer's aggregation SQL), summarization, RAG answer synthesis, and reranking. The **embedding** side is used both when a document is first ingested (to build its searchable vectors) and every time a user asks a `rag`-routed question (to embed the question itself for the kNN search).

## Why this design is good

- **Single Responsibility Principle:** `ModelService` only handles raw Bedrock communication; `LLMService`/`EmbeddingService` only handle "what does a generic text/embedding call look like"; agents only handle "what prompt does *my* use case need."
- **Single owner of the raw client:** only `ModelService` ever constructs a `boto3` Bedrock client or calls `invoke_model` directly — no other file in the project does, which keeps AWS SDK details (and any future SDK-level changes) contained to one place.
- **Reusability:** any agent can call `self.llm_service.generate(...)` or `self.embedding_service.create_embedding(...)` without duplicating request-building or response-parsing code.
- **Maintainability:** switching Claude models, changing the embedding model, or even swapping Bedrock for another provider only requires changes in `ModelService` — every agent stays untouched.
- **Configuration-driven:** model IDs (including the inference-profile nuance above) and the AWS region come from `settings`, so different environments don't require code changes.

This three-layer split is a natural evolution of the original single-`BedrockService` design once the number of distinct LLM use cases grew past "just classification and embeddings."
