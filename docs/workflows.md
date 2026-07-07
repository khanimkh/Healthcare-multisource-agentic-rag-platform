# Guide: `structured_ingestion_workflow.py` and `document_ingestion_workflow.py`

This guide explains the purpose, flow, and functions/classes used in the two ingestion workflow files.

---

## 1. Purpose of these workflow files

These files are responsible for orchestrating ingestion workflows.

They do not implement low-level AWS logic themselves. Instead, they call services and tools such as:

- `AWSStorage`
- `DocumentStore`
- `GlueCatalog`
- `OpenSearchVectorStore`
- `BedrockService`
- `data_loader`
- `rag_utils`

In simple words:

```text
Workflow files = coordinate multiple steps together
Service files = connect to external systems
Tool files = prepare/process data
```

---

## 2. `structured_ingestion_workflow.py`

### Purpose

This file handles structured files such as CSV.

Current flow:

```text
CSV file
   ↓
Upload to S3
   ↓
Create document record in RDS
   ↓
Read CSV with pandas
   ↓
Register metadata in AWS Glue
   ↓
Update RDS status
```

### Main class

```python
class StructuredIngestionWorkflow:
```

This class controls the full structured file ingestion process.

### `__init__()`

```python
def __init__(self):
	self.storage = AWSStorage()
	self.document_store = DocumentStore()
	self.glue_catalog = GlueCatalog()
```

Initializes the services needed for structured ingestion.

| Service | Purpose |
| --- | --- |
| `AWSStorage` | Uploads file to S3 |
| `DocumentStore` | Stores file metadata/status in RDS |
| `GlueCatalog` | Registers CSV schema/location in AWS Glue |

### `ingest_csv()`

```python
def ingest_csv(self, file_path: str, file_name: str) -> Dict[str, Any]:
```

Processes one CSV file.

Input:

| Parameter | Meaning |
| --- | --- |
| `file_path` | Local path of the uploaded file |
| `file_name` | Original filename |

Example:

```python
file_path = "/tmp/patients.csv"
file_name = "patients.csv"
```

#### Step 1: Upload to S3

```python
upload_result = self.storage.upload_file_to_s3(
	file_path=file_path,
	file_name=file_name
)
```

Returns:

```python
{
	"file_id": "...",
	"file_name": "...",
	"s3_key": "...",
	"s3_uri": "..."
}
```

#### Step 2: Create RDS document record

```python
self.document_store.create_document(
	file_id=file_id,
	file_name=file_name,
	s3_uri=s3_uri,
	document_type="structured_dataset"
)
```

Creates a row in PostgreSQL:

```text
file_id
file_name
s3_uri
document_type
status = uploaded
uploaded_at
```

RDS is used for application metadata, not for storing the CSV data itself.

#### Step 3: Update status to processing

```python
self.document_store.update_status(
	file_id=file_id,
	status="processing"
)
```

The file is now marked as being processed.

#### Step 4: Read CSV

```python
df = pd.read_csv(file_path)
```

The CSV is loaded as a pandas DataFrame. This is needed because Glue needs the schema:

```text
column names
column types
```

#### Step 5: Register Glue table

```python
table_name = self.glue_catalog.register_csv_table(
	dataset_name=dataset_name,
	s3_uri=s3_uri,
	df=df
)
```

Glue stores:

```text
table name
columns
data types
S3 location
CSV format
```

Glue does not store the actual CSV rows. The actual CSV is stored in S3.

#### Step 6: Update status to registered

```python
self.document_store.update_status(
	file_id=file_id,
	status="registered",
	document_type="structured_dataset"
)
```

This means the structured dataset is ready for Athena queries.

Return value:

```python
return {
	"status": "registered",
	"file_id": file_id,
	"file_name": file_name,
	"s3_uri": s3_uri,
	"glue_database": settings.glue_database_name,
	"glue_table": table_name,
	"rows": len(df),
	"columns": list(df.columns)
}
```

### `ingest()`

```python
def ingest(self, file_path: str, file_name: str) -> Dict[str, Any]:
```

Generic entry point for structured file ingestion. Currently it supports only `.csv`.

```python
extension = Path(file_name).suffix.lower()

if extension == ".csv":
	return self.ingest_csv(file_path, file_name)

raise ValueError(f"Unsupported structured file type: {extension}")
```

Later you can add Excel or Parquet support.

---

## 3. `document_ingestion_workflow.py`

### Purpose

This file handles unstructured documents such as PDF, DOCX, and TXT.

Current flow:

```text
Document file
   ↓
Upload to S3
   ↓
Create document record in RDS
   ↓
Extract text
   ↓
Classify document type
   ↓
Split text into chunks
   ↓
Create embeddings
   ↓
Bulk index chunks into OpenSearch
   ↓
Update RDS status
```

### Main class

```python
class DocumentIngestionWorkflow:
```

This class controls the full document ingestion process.

### `__init__()`

```python
def __init__(self):
	self.storage = AWSStorage()
	self.vector_store = OpenSearchVectorStore()
	self.bedrock = BedrockService()
	self.document_store = DocumentStore()
```

| Service | Purpose |
| --- | --- |
| `AWSStorage` | Uploads original document to S3 |
| `OpenSearchVectorStore` | Stores chunk embeddings in OpenSearch |
| `BedrockService` | Classifies text and creates embeddings |
| `DocumentStore` | Tracks document status in RDS |

### `ingest()`

```python
def ingest(self, file_path: str, file_name: str) -> Dict[str, Any]:
```

Processes one unstructured document.

#### Step 1: Upload to S3

```python
upload_result = self.storage.upload_file_to_s3(
	file_path=file_path,
	file_name=file_name
)
```

Example S3 location:

```text
s3://bucket/uploads/<file_id>/clinical_guideline.pdf
```

#### Step 2: Create RDS document record

```python
self.document_store.create_document(
	file_id=file_id,
	file_name=file_name,
	s3_uri=s3_uri,
	document_type="document"
)
```

Initial status is `uploaded`.

#### Step 3: Update status to processing

```python
self.document_store.update_status(
	file_id=file_id,
	status="processing"
)
```

This indicates that extraction, chunking, embedding, and indexing are in progress.

#### Step 4: Extract text

```python
text = load_document(file_path)
```

This calls the data loader. Depending on file type, it may load PDF, DOCX, or TXT.

If no text is found:

```python
raise ValueError("No text could be extracted from the document.")
```

#### Step 5: Classify document type

```python
document_type = self.bedrock.classify_text(text)
```

Bedrock classifies the document into categories such as:

```text
clinical guideline
patient report
claims dataset
healthcare policy
research publication
lab result
administrative document
unknown
```

#### Step 6: Chunk document text

```python
text_chunks = chunk_documents(text)
```

This splits long text into smaller chunks.

#### Step 7: Create embeddings

```python
embedded_chunks = create_embeddings_for_chunks(text_chunks)
```

Each chunk becomes:

```python
{
	"text": "chunk text...",
	"embedding": [0.12, -0.54, ...]
}
```

#### Step 8: Bulk index into OpenSearch

```python
self.vector_store.index_chunks(
	chunks=embedded_chunks,
	file_id=file_id,
	file_name=file_name,
	document_type=document_type,
	s3_uri=s3_uri,
	metadata={
		"source": "user_upload",
		"file_extension": Path(file_name).suffix.lower()
	},
	batch_size=500
)
```

Each chunk stores:

```text
chunk_id
file_id
chunk_index
file_name
document_type
text
embedding
s3_uri
uploaded_at
metadata
```

The important improvement is bulk indexing:

```text
500 chunks = usually 1 batch request instead of 500 separate OpenSearch requests
```

#### Step 9: Update status to indexed

```python
self.document_store.update_status(
	file_id=file_id,
	status="indexed",
	document_type=document_type
)
```

Now the document is available for RAG search.

Return value:

```python
return {
	"status": "indexed",
	"file_id": file_id,
	"file_name": file_name,
	"s3_uri": s3_uri,
	"document_type": document_type,
	"chunks_indexed": len(embedded_chunks)
}
```

---

## 4. Status lifecycle

Both workflows update document status in RDS.

| Status | Meaning |
| --- | --- |
| `uploaded` | File was uploaded and RDS record was created |
| `processing` | The ingestion pipeline is running |
| `registered` | Structured dataset was registered in Glue |
| `indexed` | Document chunks were indexed in OpenSearch |
| `failed` | Ingestion failed |

---

## 5. Difference between the two workflow files

| File | Handles | Final storage |
| --- | --- | --- |
| `structured_ingestion_workflow.py` | CSV / structured datasets | S3 + Glue + Athena |
| `document_ingestion_workflow.py` | PDF / DOCX / TXT | S3 + OpenSearch |

Both use RDS only for tracking metadata and status.

---

## 6. How they are used from API routes

Example upload route:

```python
from pathlib import Path

from app.backend.workflows.document_ingestion_workflow import DocumentIngestionWorkflow
from app.backend.workflows.structured_ingestion_workflow import StructuredIngestionWorkflow


def ingest_uploaded_file(file_path: str, file_name: str):
	extension = Path(file_name).suffix.lower()

	if extension in [".csv"]:
		workflow = StructuredIngestionWorkflow()
		return workflow.ingest(file_path, file_name)

	if extension in [".pdf", ".docx", ".txt"]:
		workflow = DocumentIngestionWorkflow()
		return workflow.ingest(file_path, file_name)

	raise ValueError(f"Unsupported file type: {extension}")
```

---

## 7. Summary

```text
structured_ingestion_workflow.py
= prepares structured datasets for Athena by uploading to S3 and registering in Glue

document_ingestion_workflow.py
= prepares unstructured documents for RAG by uploading to S3, chunking, embedding, and indexing in OpenSearch

document_store_service.py
= tracks status and metadata for both workflows in RDS
```
