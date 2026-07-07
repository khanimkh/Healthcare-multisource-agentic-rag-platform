# Final architecture

Original plan on this page: route every high-level AI task (classification, summarization, entity extraction, SQL generation, etc.) through a single `BedrockService` sitting on top of `ModelService`. What actually got built splits that high-level layer in two instead of keeping it as one class:

```text
Ingestion (rag_utils.py,
document_ingestion_workflow.py,
structured_ingestion_workflow.py)      Agents (router, rag, sql, s3,
    │                                  summarization, final answer)
    ▼                                       │
ClassificationAgent  EmbeddingService       ▼
    │                    │             LLMService
    └────────┬───────────┘                  │
             ▼                              │
        ModelService  ◄──────────────────────
             │
             ▼
     Amazon Bedrock Runtime
```

`bedrock_service.py` itself was removed once its two responsibilities (`classify_text`, `create_embedding`) moved to `ClassificationAgent` and `EmbeddingService` respectively — keeping it around as a passthrough with no distinct responsibility of its own would have violated the same Single Responsibility Principle this page argues for.

### Responsibilities

| Class | Responsibility |
|---|---|
| **ModelService** | Low-level model inference (text generation and embeddings). It knows how to call Bedrock but knows nothing about healthcare or prompts. The only file that owns the raw `boto3` `bedrock-runtime` client. |
| **EmbeddingService** | Turns text into a vector. Used by ingestion (chunk embeddings) and, later, retrieval (embedding the user's question). |
| **ClassificationAgent** | Classifies documents and structured datasets into a category, via `LLMService` + `prompts/classification_prompt.py`. |
| **LLMService** | Generic prompt-to-answer generation for agents that reason (router, rag, sql, s3, summarization, final answer). |

See `docs/design-code-general-structure.md` ("AI service layering") for the full breakdown.
