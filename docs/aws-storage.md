# Embeding and chunking

For a professional RAG system, **one index is usually the right starting design** when all documents belong to the same application/domain, for example:

```text
Healthcare RAG platform
-> one index: healthcare_documents
```

Then you use metadata filters:

```text
file_name
document_type
user_id
organization_id
upload_date
source_type
```

Example:

```text
Search only clinical guidelines
Search only one user's documents
Search only PDFs
Search only documents uploaded this month
```

---

Multi-index is used when you have clearly different collections, such as:

```text
clinical_guidelines_index
patient_reports_index
claims_data_index
research_papers_index
```

or when you need strong separation:

```text
one index per customer
one index per tenant
one index per environment
```

Example:

```text
customer_A_index
customer_B_index
```

That is useful for security, scale, or very different schemas.
----------------------

If you upload many files over time, the index grows:

```text
100 files -> maybe 5,000 chunks
1,000 files -> maybe 50,000 chunks
10,000 files -> maybe 500,000 chunks
```

That is normal. OpenSearch is designed for large indexes. But later you may need:

```text
bulk indexing instead of one-by-one indexing
metadata filtering
index lifecycle management
deduplication
deletion by file_id
monitoring search latency
shards/replicas tuning
```

For many files, professional code usually uses **bulk indexing** instead of indexing one chunk at a time.

---------------

## Your current code already uses **bulk indexing**

This project's `OpenSearchVectorStore.index_chunks()` (in `app/backend/services/aws_storage_service.py`) builds a list of index actions in memory, one per chunk, and sends them all to OpenSearch in a single `helpers.bulk()` call instead of looping over `self.client.index()`:

```python
actions = []

for chunk_index, chunk in enumerate(chunks):
	chunk_id = f"{file_id}_{chunk_index}"

	document = {
		"text": chunk["text"],
		"file_id": file_id,
		"chunk_id": chunk_id,
		"chunk_index": chunk_index,
		"file_name": file_name,
		"document_type": document_type,
		"s3_uri": s3_uri,
		"uploaded_at": uploaded_at,
		"metadata": metadata,
		"embedding": chunk["embedding"],
	}

	actions.append({
		"_op_type": "index",
		"_index": settings.opensearch_index,
		"_id": chunk_id,
		"_source": document,
	})

helpers.bulk(self.client, actions, chunk_size=batch_size)
```

In practice this means: for a document with 500 chunks, the app makes roughly `500 / batch_size` bulk requests (with the default `batch_size=500`, that's a single request) instead of 500 separate ones — the exact shape recommended above. A few details worth calling out:

- **Deterministic `_id`** — each chunk's OpenSearch document ID is `f"{file_id}_{chunk_index}"` rather than an auto-generated ID. This makes re-indexing the same file idempotent: re-running ingestion overwrites the same documents instead of creating duplicates.
- **`chunk_size` batching** — `helpers.bulk()`'s `chunk_size` parameter (wired to the `batch_size` argument, default 500) caps how many actions go in one HTTP request, so a single very large document doesn't produce one unbounded request; it's split into multiple bulk requests of at most `chunk_size` actions each.
- **Where it's called from** — `DocumentIngestionWorkflow` calls `index_chunks()` once per uploaded document with that document's full chunk list, so bulk indexing happens per upload, not across uploads. Batching many separate uploads into one bulk call is a further optimization this project doesn't do, since ingestion is triggered per-file as users upload.

---

# Why does bulk indexing matter?

Without it, every chunk means a separate request: Python has to build the request, authenticate with AWS, send it over the network, and wait for OpenSearch's response — one full round trip per chunk. At roughly 20ms overhead per request, a 500-chunk document would cost about 10 seconds just in request overhead, most of which is network/auth overhead rather than actual storage time.

Bulk indexing collapses that into one request carrying many documents at once (`Chunk 1 ... Chunk 500 → One Bulk Request → OpenSearch`), which is why the current implementation batches all of a document's chunks into a single `helpers.bulk()` call instead of calling `self.client.index()` per chunk.

---------------


