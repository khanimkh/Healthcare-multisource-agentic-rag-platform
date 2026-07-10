# Final architecture

> This doc matches the current code in `app/backend/services/model_service.py`, `app/backend/services/llm_service.py`, `app/backend/services/embedding_service.py`, and `app/backend/agents/*.py`. See also `docs/bedrock-service.md` for a line-by-line walkthrough of `ModelService`/`LLMService`/`EmbeddingService`.

Original plan on this page: route every high-level AI task (classification, summarization, entity extraction, SQL generation, etc.) through a single `BedrockService` sitting on top of `ModelService`. What actually got built splits that high-level layer in two instead of keeping it as one class — and **`ClassificationAgent` is just another `LLMService` consumer**, not a separate direct-to-`ModelService` path (an earlier version of this doc drew it that way, which didn't match `classification_agent.py`'s actual `self.llm_service = LLMService()`):

```text
Ingestion workflows                              Agents that reason
(document_ingestion_workflow.py,                 (router, rag, sql, s3, chart,
 structured_ingestion_workflow.py,                classification, summarization,
 rag_utils.py)                                    final_answer, graph_rag)
    │                                                       │
    ├──► ClassificationAgent ─────────────────────┐         │
    │      (classify_document /                    ▼         ▼
    │       classify_structured_data)          LLMService.generate()
    │                                                       │
    └──► EmbeddingService.create_embedding()                │
              │                                              │
              ▼                                              ▼
         ModelService.invoke_embedding_model()   ModelService.invoke_text_model()
              │                                              │
              └──────────────────────┬───────────────────────┘
                                      ▼
                          Amazon Bedrock Runtime
```

`bedrock_service.py` itself was removed once its two responsibilities (`classify_text`, `create_embedding`) moved to `ClassificationAgent` and `EmbeddingService` respectively — keeping it around as a passthrough with no distinct responsibility of its own would have violated the same Single Responsibility Principle this page argues for.

### Responsibilities

| Class | Responsibility |
|---|---|
| **ModelService** | Low-level model inference (text generation and embeddings). It knows how to call Bedrock but knows nothing about healthcare or prompts. The only file that owns the raw `boto3` `bedrock-runtime` client. |
| **EmbeddingService** | Turns text into a vector via `ModelService.invoke_embedding_model()`. Used by ingestion (`rag_utils.py`'s `create_embeddings_for_chunks()`, one call per chunk) and by `RAGAgent.retrieve()` (embedding the user's question at query time — no longer a "later" item, this is live). |
| **ClassificationAgent** | Classifies documents (`classify_document()`) and structured datasets (`classify_structured_data()`) into a category, via `LLMService` + `prompts/classification_prompt.py`. Called from three places: `document_ingestion_workflow.py` and `structured_ingestion_workflow.py` at upload time, and `classify_uploaded_document()` (resolves a named document, then classifies it) from the chat `classification` route in `question_graph.py`. |
| **LLMService** | Generic prompt-to-answer generation, called by every agent that talks to Claude: `router_agent.py`, `rag_agent.py`, `sql_agent.py`, `s3_agent.py`, `chart_agent.py`, `classification_agent.py`, `summarization_agent.py`, `final_answer_agent.py`, and `graph_rag_agent.py` — nine consumers as of this writing, not just the original four or five. |

See `docs/design-code-general-structure.md` ("AI service layering") for the full breakdown.
