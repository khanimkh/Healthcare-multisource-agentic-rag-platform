# Step 1. User uploads a file

```text
Client
  │
  ▼
POST /upload
```

Example uploads:

- `patients.csv`
- `report.pdf`
- `xray.png`

---

# Step 2. File is temporarily saved locally

```python
with open(local_path, "wb") as buffer:
	shutil.copyfileobj(file.file, buffer)
```

The file is first saved on the application server.

Example:

```text
app/backend/data/raw/
	  │
	  └── 34ac12_report.pdf
```

This local copy is only temporary.

---

# Step 3. The original file is uploaded to S3 ✅

```python
s3_uri = aws_storage.upload_file_to_s3(local_path, s3_key)
```

where:

```python
s3_key = f"raw/{file_id}/{original_file_name}"
```

Example:

```text
S3 Bucket
raw/
   34ac12/
		report.pdf
```

The returned value might be:

```text
s3://healthcare-bucket/raw/34ac12/report.pdf
```

So **yes, every uploaded file is stored in Amazon S3.**

---

# Step 4. The file is processed

Depending on the file type:

### Structured file

```text
CSV
 ↓
Clean dataframe
 ↓
Classify
 ↓
Save into PostgreSQL
```

---

### Document or image

```text
PDF
 ↓
Extract text
 ↓
Clean text
 ↓
Classify
 ↓
Chunk
 ↓
Embedding
 ↓
OpenSearch
```

---

# Step 5. Metadata is registered in the Glue Catalog

This happens here:

```python
glue_registered = glue_catalog.register_metadata(...)
```

Notice what metadata is passed:

```python
metadata = {
	"document_type": document_type,
	"file_id": file_id,
	"rds_table": rds_table,
	"opensearch_index": opensearch_index,
	"chunks_created": chunks_created,
}
```

Also outside the metadata object:

```python
dataset_name = original_file_name
s3_uri = s3_uri
file_type = file_type
```

So the Glue Catalog receives information similar to:

```text
Field               Example
dataset_name        report.pdf
S3 URI              s3://bucket/raw/...
file_type           document
document_type       clinical guideline
file_id             34ac12...
rds_table           dataset_34ac12
OpenSearch index    healthcare-documents
chunks_created      18
```

---

# Step 6. Metadata is cached in Redis

Later:

```python
cache.set_json(...)
```

stores:

```python
{
	"file_name": ...,
	"file_type": ...,
	"document_type": ...,
	"s3_uri": ...,
	"rds_table": ...,
	"opensearch_index": ...,
}
```

Redis is **not permanent storage**.

It is only used for faster access.

---

# What is stored where?

## Amazon S3

Stores the **original file**.

Example:

```text
report.pdf
patients.csv
image.png
```

---

## PostgreSQL (only structured files)

Stores the cleaned table.

Example:

```text
Patients Table
Age | Gender | Diagnosis | ...
```

---

## OpenSearch (documents/images)

Stores:

- chunks
- embeddings
- metadata

Example:

```text
Chunk 1 | Embedding | File name | Document type
```

---

## Glue Catalog

Stores metadata describing the dataset.

It does **not** store the actual document.

Think of it as a catalog or inventory.

Example:

```text
Dataset Name
   ↓
S3 Location
   ↓
Document Type
   ↓
RDS Table
   ↓
OpenSearch Index
```

---

## Redis

Stores temporary metadata for quick retrieval.

---

# Overall Architecture

```text
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
	 Structured       Document/Image
		  │                 │
		  ▼                 ▼
	  PostgreSQL        OpenSearch
		  │                 │
		  └────────┬────────┘
				   ▼
		  Glue Metadata Catalog
				   │
				   ▼
			   Redis Cache
```
---------------------------------

# Overall Architecture

The workflow of this endpoint looks like this:

```text
										Client
											│
							POST /upload
											│
											▼
						 FastAPI Router (this file)
											│
			┌───────────────┼────────────────┐
			▼               ▼                ▼
 Save locally     Detect type     Load content
			│
			▼
 Upload to S3
			│
			▼
 Is Structured?
			│
 ┌────┴─────────────┐
 │                  │
 ▼                  ▼
Structured      Document/Image
 │                  │
 ▼                  ▼
Clean Data      Clean Text
 │                  │
 ▼                  ▼
Classify         Classify
 │                  │
 ▼                  ▼
Save to RDS     Chunk + Embed
 │                  │
 ▼                  ▼
						 OpenSearch
										│
										▼
						 Register in Glue
										│
										▼
						 Cache Metadata
										│
										▼
					Return UploadResponse
```

---

# Imports

The imports are grouped by responsibility.

## 1. Python Standard Library

```python
import os
import uuid
import shutil
```

These are built into Python.

### os

Used for working with files and folders.

Examples:

```python
os.makedirs(...)
```

Create directories.

```python
os.path.join(...)
```

Build file paths safely.

---

### uuid

Creates unique IDs.

Example:

```python
uuid.uuid4()
```

returns something like:

```text
6fd8e5d8-1d8e-4b5e-bb6c-1d4d39e8d321
```

Each uploaded file gets a unique identifier.

---

### shutil

Used for copying files.

Here:

```python
shutil.copyfileobj(...)
```

copies the uploaded file into local storage.

---

## 2. FastAPI

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
```

These classes provide the API functionality.

### APIRouter

Groups endpoints together.

Example:

```python
router = APIRouter()
```

Later:

```python
app.include_router(router)
```

adds these endpoints to the application.

---

### UploadFile

Represents an uploaded file.

Instead of receiving text,

the endpoint receives:

```text
report.pdf
```

or:

```text
patients.csv
```

---

### File(...)

Tells FastAPI that this parameter is a file upload.

---

### HTTPException

Returns HTTP errors.

Example:

```python
raise HTTPException(
		status_code=400,
		detail="Unsupported file",
)
```

---

# Response Schema

```python
from app.backend.schemas.upload_schema import UploadResponse
```

Instead of returning a raw dictionary,

the endpoint returns a validated Pydantic model.

---

# Tool Imports

These are helper modules that perform specialized tasks.

### Data Loader

```python
detect_file_type()
load_data()
clean_dataframe()
clean_text()
```

Responsible for:

- detecting the file type
- reading the file
- cleaning tabular data
- cleaning extracted text

---

### AWS Storage

```python
AWSStorage()
```

Uploads files to S3.

---

### OpenSearch

```python
OpenSearchVectorStore()
```

Stores embeddings for semantic search.

---

### Database

```python
RDSStorage()
```

Stores structured datasets in PostgreSQL.

---

### RAG Utilities

```python
chunk_documents()
create_embeddings_for_chunks()
```

Used only for text documents.

Workflow:

```text
Document
	↓
Chunk
	↓
Embedding
	↓
Vector Database
```

---

### Glue Catalog

Registers dataset metadata.

---

### Classification Agent

Uses an LLM to classify documents.

Example:

```text
clinical guideline
patient report
claims dataset
```

---

### Cache Service

Stores upload metadata in Redis.

---

# Router

```python
router = APIRouter()
```

Creates the router.

---

# Upload Directory

```python
UPLOAD_DIR = ...
```

Temporary local folder before uploading to S3.

---

# Endpoint

```python
@router.post("/upload")
```

Creates:

```text
POST /upload
```

---

# Function

```python
async def upload_file(...)
```

Receives:

```text
multipart/form-data
```

containing one uploaded file.

---

# Create Upload Folder

```python
os.makedirs(...)
```

Creates:

```text
app/backend/data/raw
```

if it doesn't already exist.

---

# Generate File ID

```python
file_id = uuid.uuid4()
```

Every upload gets a unique ID.

Example:

```text
report.pdf
	 ↓
82af....
	 ↓
82af_report.pdf
```

---

# Save File Locally

```python
with open(...)
```

Creates a file.

```python
shutil.copyfileobj(...)
```

Copies uploaded bytes into that file.

---

# Detect File Type

```python
file_type = detect_file_type(...)
```

Possible results:

```text
structured
document
image
unknown
```

---

# Unsupported File

```python
if file_type == "unknown":
```

Immediately returns HTTP 400.

---

# Initialize Services

```python
aws_storage = AWSStorage()
classifier = ClassificationAgent()
cache = CacheService()
```

Creates reusable service objects.

---

# Upload to S3

```python
s3_uri = aws_storage.upload_file_to_s3(...)
```

Stores original file.

Example:

```text
local
	↓
S3
	↓
s3://bucket/raw/...
```

---

# Load File

```python
loaded_data = load_data(...)
```

Different readers depending on extension.

```text
CSV -> DataFrame
PDF -> Text
Image -> OCR text
```

---

# Metadata

```python
response_metadata
```

Stores extra information for the response.

---

# Initialize Variables

```python
document_type = None
```

These variables will later be filled depending on file type.

---

# Structured Data Workflow

```python
if file_type == "structured":
```

Steps:

```text
CSV
 ↓
Clean
 ↓
Classify
 ↓
Save into PostgreSQL
```

---

### Clean

```python
clean_dataframe(...)
```

Removes invalid values.

---

### Classification

```python
classifier.classify_structured_data(...)
```

LLM determines dataset type.

---

### Save

```python
rds.save_dataframe(...)
```

Stores table inside PostgreSQL.

---

### Metadata

Stores:

```text
columns
rows
```

---

# Document/Image Workflow

```python
elif file_type in ["document", "image"]:
```

Pipeline:

```text
Document
 ↓
Extract text
 ↓
Clean text
 ↓
Classify
 ↓
Chunk
 ↓
Embedding
 ↓
OpenSearch
```

---

### Clean Text

```python
clean_text(...)
```

Removes unnecessary formatting.

---

### Classification

```text
Research paper
Patient report
Guideline
```

---

### Chunking

```python
chunk_documents(...)
```

Large text
 ↓
Small chunks

---

### Embeddings

```python
create_embeddings_for_chunks(...)
```

Each chunk
 ↓
Vector

---

### OpenSearch

```python
index_chunks(...)
```

Stores vectors for future semantic retrieval.

---

# Glue Registration

```python
glue_catalog.register_metadata(...)
```

Registers metadata such as:

- S3 location
- file type
- document type
- RDS table
- OpenSearch index

This makes datasets discoverable for downstream analytics.

---

# Cache

```python
cache.set_json(...)
```

Stores frequently needed metadata in Redis.

Purpose:

```text
Next request
	 ↓
Redis
	 ↓
No database query
```

---

# Response

Finally returns:

```python
UploadResponse(...)
```

This matches the schema:

```text
status
file name
S3 URI
RDS table
OpenSearch index
metadata
```

---

# Error Handling

```python
except Exception as e:
```

Any unexpected error becomes:

```text
HTTP 500 Internal Server Error
```

with the error message.

---

# Why is this router designed this way?

This router acts as the **orchestrator** of your upload pipeline. It doesn't perform OCR, generate embeddings, query Bedrock, or execute SQL itself. Instead, it coordinates specialized components, each with a single responsibility:

- **Router**: Receives the HTTP request, validates it, coordinates the workflow, and returns the response.
- **Data Loader**: Reads and cleans uploaded files.
- **Classification Agent**: Uses the LLM to identify the document type.
- **AWS Storage**: Uploads files to Amazon S3.
- **RDS Storage**: Stores structured datasets in PostgreSQL.
- **RAG Utilities**: Splits documents into chunks and generates embeddings.
- **OpenSearch Vector Store**: Indexes embeddings for semantic search.
- **Glue Catalog**: Registers dataset metadata.
- **Cache Service**: Stores frequently accessed metadata in Redis.

This separation of concerns makes the application easier to maintain, test, and extend. For example, if you later switch from OpenSearch to another vector database or from Bedrock to another LLM provider, most changes will be isolated to the corresponding service class rather than this API endpoint.
