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

Your current code indexes one chunk at a time:

```python
self.client.index(...)
```

For many files, professional code usually uses **bulk indexing**.

---------------

## Your current code uses **single indexing**

Look at the loop:

```python
for chunk in chunks:
	body = {
		"text": chunk["text"],
		"file_name": file_name,
		"document_type": document_type,
		"embedding": chunk["embedding"],
	}
	self.client.index(
		index=settings.opensearch_index,
		body=body,
	)
```

Notice that `self.client.index()` is called **inside the loop**.

That means:

```text
Chunk 1
   │
   ▼
OpenSearch request #1

Chunk 2
   │
   ▼
OpenSearch request #2

Chunk 3
   │
   ▼
OpenSearch request #3

Chunk 4
   │
   ▼
OpenSearch request #4
```

If your document has 500 chunks, your application sends:

```text
500 separate HTTP requests
```

to OpenSearch.

This is called **single indexing** (or one document per request).

---

# Why is this slower?

Every request has overhead.

For every chunk, Python has to:

1. Create an HTTP request
2. Authenticate with AWS
3. Send it over the network
4. Wait for OpenSearch
5. Receive the response
6. Repeat for the next chunk

Suppose one request takes only **20 milliseconds**.

For 500 chunks:

```text
20 ms × 500 = 10 seconds
```

Most of that time is spent sending requests, not storing data.

---

# What is Bulk Indexing?

Instead of sending 500 requests,

you send **one request containing 500 documents**.

Like this:

```text
Chunk 1
Chunk 2
Chunk 3
...
Chunk 500
	│
	▼
One Bulk Request
	│
	▼
OpenSearch
```

Instead of:

```text
500 HTTP requests
```

you send:

```text
1 HTTP request
```

(or maybe a few large ones).

This is much faster.

---

# How does professional code look?

Instead of:

```python
for chunk in chunks:
	self.client.index(...)
```

you first build a list.

Imagine:

```python
actions = [
	{
		"_index": "healthcare_documents",
		"_source": {...},
	},
	{
		"_index": "healthcare_documents",
		"_source": {...},
	},
	{
		"_index": "healthcare_documents",
		"_source": {...},
	},
]
```

Then call:

```python
helpers.bulk(client, actions)
```

---------------


