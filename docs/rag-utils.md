## `rag_utils.py` -> Data preparation layer

Its responsibility is to **prepare data for vector storage**.

It contains functions like:

- Read/clean text (if needed)
- Split text into chunks
- Create embeddings
- Other preprocessing

It knows **nothing** about where the data will be stored.

```text
Document
	│
	▼
Read text
	│
	▼
Chunk text
	│
	▼
Create embeddings
	│
	▼
Prepared data
```

So you can say:

> **rag_utils.py prepares the data for vector storage.**

---

## `aws_storage.py` -> AWS infrastructure layer

Its responsibility is to **communicate with AWS services**.

It contains functions like:

- Upload file to S3
- Create OpenSearch index
- Bulk index vectors
- (Later) Delete vectors
- (Later) Search vectors
- (Later) Download files from S3

It **doesn't know how to chunk text or create embeddings**. It only stores and retrieves data.

```text
Prepared data
	  │
	  ▼
Upload to S3
	  │
	  ▼
Create OpenSearch index
	  │
	  ▼
Bulk index vectors
```

So you can say:

> **aws_storage.py is responsible for interacting with AWS services (S3 and OpenSearch).**

---

## Together

The architecture becomes:

```text
					 PDF
					  │
					  ▼
			 rag_utils.py
────────────────────────────────
Load document
Chunk document
Create embeddings
────────────────────────────────
					  │
		Prepared chunks + vectors
					  │
					  ▼
			aws_storage.py
────────────────────────────────
Upload file to S3
Create OpenSearch index
Bulk index vectors
────────────────────────────────
					  │
					  ▼
				 AWS Cloud
```

--------------------------

They are used in **different stages** of the RAG pipeline.

```text
PDF text
   │
   ▼
chunk_documents()
   │
   ▼
create_embeddings_for_chunks()
   │
   ▼
create_index_if_not_exists()
   │
   ▼
index_chunks()
   │
   ▼
OpenSearch vector database
```

## 1. `chunk_documents()`

This function only splits long text into smaller pieces.

Input:

```python
text = "Long PDF text..."
```

Output:

```python
["chunk 1 text", "chunk 2 text", "chunk 3 text"]
```

It does **not** call AWS.

It does **not** save anything.

---

## 2. `create_embeddings_for_chunks()`

This function converts each text chunk into a vector using Bedrock.

Input:

```python
["chunk 1 text", "chunk 2 text"]
```

Output:

```python
[
	{
		"text": "chunk 1 text",
		"embedding": [0.12, -0.45, ...],
	},
	{
		"text": "chunk 2 text",
		"embedding": [0.34, 0.88, ...],
	},
]
```

It calls Bedrock.

It does **not** save to OpenSearch.

---

## 3. `create_index_if_not_exists()`

This function creates the OpenSearch index/schema if it does not already exist.

It defines:

```text
"text": text field
"file_id": keyword field
"file_name": keyword field
"embedding": vector field
```

It prepares OpenSearch to accept vector documents.

It does **not** store chunks.

---

## 4. `index_chunks()`

This function saves embedded chunks into OpenSearch.

Input:

```python
[
	{
		"text": "chunk 1 text",
		"embedding": [...],
	}
]
```

Then it adds metadata:

```text
file_id
file_name
document_type
s3_uri
uploaded_at
chunk_id
```

Then it bulk inserts into OpenSearch.

---

So in simple words:

```text
chunk_documents = cut the text
create_embeddings_for_chunks = turn text into vectors
create_index_if_not_exists = prepare OpenSearch table/index
index_chunks = save vectors into OpenSearch
```

----------------------------
