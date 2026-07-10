> Updated to match the current code. Two things changed since this doc was first written: `aws_storage.py` doesn't exist anymore — it's `app/backend/services/aws_storage_service.py`, and its functions are methods on two classes (`AWSStorage`, `OpenSearchVectorStore`), not free functions. See `docs/aws-storage.md` for the bulk-indexing details and `docs/bedrock-service.md` for how embeddings actually reach Bedrock.

## `tools/rag_utils.py` -> chunking + embedding, nothing else

Its responsibility is narrower than "data preparation" in general — it's exactly two functions, both stateless, neither touching AWS directly:

```python
def chunk_documents(text: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def create_embeddings_for_chunks(chunks: List[str]) -> List[Dict[str, Any]]:
    embedding_service = EmbeddingService()
    embedded_chunks = []

    for chunk in chunks:
        embedding = embedding_service.create_embedding(chunk)
        embedded_chunks.append({"text": chunk, "embedding": embedding})

    return embedded_chunks
```

It knows **nothing** about where the data will be stored (no OpenSearch, no S3), and **nothing** about how to extract text from a file in the first place — that's `tools/data_loader.py` (see `docs/load-data.md`), a separate module. `rag_utils.py` only takes plain text that's already been extracted and turns it into chunks, then vectors.

```text
Plain text (already extracted by data_loader.py)
        │
        ▼
chunk_documents()
        │
        ▼
create_embeddings_for_chunks()
        │
        ▼
[{text, embedding}, ...]
```

So you can say:

> **`rag_utils.py` chunks text and embeds chunks — it doesn't load files and it doesn't store anything.**

### `chunk_documents()`

Splits text using LangChain's `RecursiveCharacterTextSplitter`, not a hand-rolled splitter — it tries to break on paragraph/sentence boundaries first and only falls back to a hard character cut if a piece is still too long. Two real, distinct callers with different parameters:

| Caller | `chunk_size` / `chunk_overlap` | Why |
| --- | --- | --- |
| `document_ingestion_workflow.py` | defaults (`1000` / `150`) | Standard RAG chunking for indexing into OpenSearch |
| `summarization_agent.py`'s `summarize()` (map-reduce, see `docs/question-graph-agents-prompts.md`) | `chunk_size=6000, chunk_overlap=200` (its `MAP_REDUCE_THRESHOLD`) | Reuses the same splitter for a completely different purpose — breaking a long document into large pieces that each fit under the summarization prompt's size limit, not into small retrieval-sized chunks |

Same function, two call sites, two different chunk sizes for two different jobs — this is why `chunk_size`/`chunk_overlap` are parameters rather than hardcoded constants.

### `create_embeddings_for_chunks()`

Loops over the given text chunks and calls `EmbeddingService.create_embedding()` once per chunk — this is **not** a batch embedding call; Titan Embeddings' `invoke_model` only accepts one `inputText` per request (same limitation noted in `docs/bedrock-service.md` for `EmbeddingService.create_embeddings()`, the plural convenience method this function predates and duplicates). `rag_utils.py` never touches `boto3` or Bedrock's request shape directly — it goes through `EmbeddingService` → `ModelService.invoke_embedding_model()`, the same layering every other embedding call in the project uses.

Only caller: `document_ingestion_workflow.py`, right after `chunk_documents()`.

---

## `services/aws_storage_service.py` -> AWS infrastructure layer

Two classes, not free functions — each owning its own `boto3`/OpenSearch client (the "single owner of the raw client" pattern used throughout this project):

### `AWSStorage` — S3 only

| Method | Does |
| --- | --- |
| `upload_file_to_s3(file_path, file_name)` | Generates a `file_id` (UUID), uploads to `uploads/{file_id}/{file_name}` in the configured bucket, returns `{file_id, file_name, s3_key, s3_uri}` |
| `delete_file(s3_uri)` | Parses the `s3://bucket/key` URI back into bucket + key and deletes the object |

### `OpenSearchVectorStore` — OpenSearch only

| Method | Does |
| --- | --- |
| `create_index_if_not_exists(dimension)` | Creates the kNN-enabled index with the full field mapping (`text`, `file_id`, `chunk_id`, `chunk_index`, `file_name`, `document_type`, `s3_uri`, `uploaded_at`, `metadata`, and `embedding` as a `knn_vector` of the given `dimension`) — a no-op if the index already exists. **Not called separately by any workflow** — it's called internally by `index_chunks()` below, the only caller |
| `index_chunks(chunks, file_id, file_name, document_type, s3_uri=None, metadata=None, batch_size=500)` | Bulk-indexes all of a document's chunks in one `helpers.bulk()` call (see `docs/aws-storage.md` for the full bulk-indexing writeup) — auto-creates the index first via `create_index_if_not_exists()` |
| `search_chunks(embedding, k=5, document_type=None)` | The kNN vector search behind the `rag` route — optionally filtered by `document_type` |
| `delete_chunks(file_id)` | Deletes every indexed chunk belonging to one file (used when a document is deleted via `DELETE /documents/{file_id}`) |
| `get_document_text(file_id)` | Fetches every indexed chunk for a file, sorted by `chunk_index`, and joins them back into the original full text — used by `SummarizationAgent`/`ClassificationAgent` to re-fetch a resolved document's full content |

It **doesn't know how to chunk text or create embeddings** — it only stores and retrieves already-prepared `{text, embedding, ...}` documents.

---

## Together: the real ingestion pipeline

`document_ingestion_workflow.py` is what wires `rag_utils.py` and `aws_storage_service.py` together — neither imports the other directly, and `OpenSearchVectorStore.index_chunks()` just accepts a plain `{text, embedding}` list without knowing or caring that `rag_utils.py` was what produced it. The actual call order, in sequence:

```text
1. AWSStorage.upload_file_to_s3()             — raw file to S3 first, so a
                                                  file_id/s3_uri exist even if
                                                  a later step fails
2. tools/data_loader.load_document()          — extract plain text
3. tools/rag_utils.chunk_documents()          — split text into chunks
4. tools/rag_utils.create_embeddings_for_chunks()
                                               — embed each chunk (via
                                                  EmbeddingService)
5. OpenSearchVectorStore.index_chunks()       — bulk-index the
                                                  [{text, embedding}, ...] list
                                                  into OpenSearch (auto-creates
                                                  the index on first call via
                                                  create_index_if_not_exists())
```

Steps 2–4 (extraction, chunking, embedding) happen entirely in memory, in the request handler, before anything touches OpenSearch — S3 upload is the only step that happens early, specifically so the uploaded file itself isn't lost if classification, entity extraction, or chunking fails partway through.
