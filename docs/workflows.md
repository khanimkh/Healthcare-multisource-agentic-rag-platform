# Guide: `structured_ingestion_workflow.py` and `document_ingestion_workflow.py`

> Updated to match the current code. Both workflows grew real steps since this doc was first written — structured ingestion gained classification and a Postgres dual-write, document ingestion gained entity/relationship graph extraction — and every "RDS" reference has been corrected to "Postgres" (this project uses a self-hosted `postgres:16-alpine` Docker container, not AWS RDS — see `docs/RDS-glue.md`).

---

## 1. Purpose of these workflow files

These files are responsible for orchestrating ingestion workflows.

They do not implement low-level AWS logic themselves. Instead, they call services and tools such as:

- `AWSStorage`, `OpenSearchVectorStore` (`services/aws_storage_service.py`, see `docs/rag-utils.md`)
- `DocumentStore` (`services/document_store_service.py`, see `docs/RDS-glue.md`)
- `GlueCatalog` (`services/glue_catalog_service.py`, see `docs/RDS-glue.md`)
- `RelationalDataStore` (`services/relational_store_service.py`) — new since this doc was first written
- `GraphStoreService` (`services/graph_store_service.py`) — new since this doc was first written
- `ClassificationAgent` (`agents/classification_agent.py`, see `docs/question-graph-agents-prompts.md`)
- `tools/data_loader.py`, `tools/rag_utils.py`, `tools/entity_extraction.py`

In simple words:

```text
Workflow files = coordinate multiple steps together
Service files  = connect to external systems
Agent files    = call the LLM
Tool files     = prepare/process data
```

---

## 2. `structured_ingestion_workflow.py`

### Purpose

This file handles structured files — currently CSV only (`.xlsx`/`.xls` are rejected, see `docs/load-data.md`).

**Current flow** — two real steps this doc previously omitted entirely, marked below:

```text
CSV file
   |
Upload to S3
   |
Create document record in Postgres (status: uploaded)
   |
Update status to processing
   |
Read CSV with pandas (via load_csv())
   |
Classify the dataset            <- classification was added after this doc was first written
   |
Register schema/location in AWS Glue   (Athena-queryable)
   |
Dual-write the DataFrame into Postgres  <- also added after this doc was first written
   |                                       (sql-route-queryable)
Update status to registered (with the classified category)
```

### Main class

```python
class StructuredIngestionWorkflow:
```

### `__init__()`

```python
def __init__(self):
    self.storage = AWSStorage()
    self.document_store = DocumentStore()
    self.glue_catalog = GlueCatalog()
    self.classification_agent = ClassificationAgent()
    self.relational_store = RelationalDataStore()
```

| Service | Purpose |
| --- | --- |
| `AWSStorage` | Uploads file to S3 |
| `DocumentStore` | Stores file metadata/status in Postgres |
| `GlueCatalog` | Registers CSV schema/location in AWS Glue, for Athena |
| `ClassificationAgent` | Classifies the dataset's category from its column names |
| `RelationalDataStore` | Dual-writes the actual DataFrame into a real Postgres table |

Two of these five (`ClassificationAgent`, `RelationalDataStore`) didn't exist in the original version of this workflow — they were added to make classification apply to structured uploads too, and to make uploaded CSVs actually queryable via the `sql` route (Postgres), not just `s3` (Athena).

### `ingest_csv()`

```python
def ingest_csv(self, file_path: str, file_name: str) -> Dict[str, Any]:
```

Processes one CSV file, step by step:

#### Step 1: Upload to S3

```python
upload_result = self.storage.upload_file_to_s3(file_path=file_path, file_name=file_name)
```

Returns `{file_id, file_name, s3_key, s3_uri}`.

#### Step 2: Create the Postgres document record

```python
self.document_store.create_document(
    file_id=file_id, file_name=file_name, s3_uri=s3_uri,
    document_type="structured_dataset"
)
```

`document_type` here is a **placeholder** — `"structured_dataset"` literally, not yet the real classified category (that comes in Step 4). See `docs/RDS-glue.md` for the exact `documents` table schema this writes to.

#### Step 3: Update status to `processing`

```python
self.document_store.update_status(file_id=file_id, status="processing")
```

#### Step 4: Read the CSV, then classify it

```python
df = load_csv(file_path)
document_type = self.classification_agent.classify_structured_data(df)
```

`load_csv()` goes through `tools/data_loader.py` (see `docs/load-data.md`), not raw `pandas` in the workflow — keeps all file-loading logic in one place. `classify_structured_data()` (`ClassificationAgent`, `docs/question-graph-agents-prompts.md`) classifies from the DataFrame's **column names only**, not its values — e.g. `patient_id, age, diagnosis, readmitted` might classify as `"patient report"`. This `document_type` is what ends up in the final `update_status()` call and the API response, replacing the `"structured_dataset"` placeholder from Step 2.

#### Step 5: Register the Glue table

```python
dataset_name = Path(file_name).stem
table_name = self.glue_catalog.register_csv_table(dataset_name=dataset_name, s3_uri=s3_uri, df=df)
```

Glue stores table name, columns, data types, and S3 location — not the actual rows. See `docs/RDS-glue.md` for `register_csv_table()`'s real implementation (column-name normalization, OpenCSVSerde config, create-or-update-table logic).

#### Step 6: Dual-write into Postgres

```python
postgres_table = self.relational_store.load_dataframe(dataset_name=dataset_name, df=df)
```

`RelationalDataStore.load_dataframe()` calls `df.to_sql(table_name, self.engine, if_exists="replace", index=False)` — the table name goes through the same `normalize_table_name()` helper Glue uses (`utils/naming.py`), so a CSV named `patients.csv` becomes both Glue table `patients` and Postgres table `patients`. This is what makes `SQLAgent` (the `sql` route) able to see and query uploaded CSVs — before this step existed, only `S3Agent`/Athena could.

#### Step 7: Update status to `registered`

```python
self.document_store.update_status(file_id=file_id, status="registered", document_type=document_type)
```

`document_type` is the real classified value from Step 4, not the `"structured_dataset"` placeholder.

### Return value

```python
sample_rows = json.loads(df.head(5).to_json(orient="records"))

return {
    "status": "registered",
    "file_id": file_id,
    "file_name": file_name,
    "s3_uri": s3_uri,
    "document_type": document_type,
    "glue_database": settings.glue_database_name,
    "glue_table": table_name,
    "postgres_table": postgres_table,
    "rows": len(df),
    "columns": list(df.columns),
    "sample_rows": sample_rows
}
```

`postgres_table` and `sample_rows` are new fields since this doc was first written — `sample_rows` uses `df.head(5).to_json(orient="records")` then `json.loads()` (not `.to_dict(orient="records")`) specifically because `to_json` handles NaN/numpy dtypes safely, where `.to_dict()` can produce values the JSON encoder chokes on. The frontend's Upload tab renders `sample_rows` as a real preview table.

### `ingest()`

```python
def ingest(self, file_path: str, file_name: str) -> Dict[str, Any]:
    extension = Path(file_name).suffix.lower()

    if extension == ".csv":
        return self.ingest_csv(file_path, file_name)

    raise ValueError(f"Unsupported structured file type: {extension}")
```

Still CSV-only, unchanged. `.xlsx`/`.xls` files reach this method (since `detect_file_type()` classifies them as `"structured"`) but are rejected here with a clean `ValueError` — see the real gap this causes, documented in `docs/load-data.md`.

---

## 3. `document_ingestion_workflow.py`

### Purpose

This file handles unstructured documents — PDF, DOCX, TXT, and (via OCR) images.

**Current flow** — one entire real step this doc previously omitted:

```text
Document/image file
   |
Upload to S3
   |
Create document record in Postgres (status: uploaded)
   |
Update status to processing
   |
Extract text (load_document() — dispatches by extension, see docs/load-data.md)
   |
Classify document type
   |
Extract entities + relationships, upsert into the knowledge graph  <- entirely
   |                                                                   missing
   |                                                                   from this
Split text into chunks                                                doc before
   |
Create embeddings
   |
Bulk index chunks into OpenSearch
   |
Update status to indexed
```

### Main class

```python
class DocumentIngestionWorkflow:
```

### `__init__()`

```python
def __init__(self):
    self.storage = AWSStorage()
    self.vector_store = OpenSearchVectorStore()
    self.classification_agent = ClassificationAgent()
    self.document_store = DocumentStore()
    self.graph_store = GraphStoreService()
```

| Service | Purpose |
| --- | --- |
| `AWSStorage` | Uploads original document to S3 |
| `OpenSearchVectorStore` | Bulk-indexes chunk embeddings, see `docs/aws-storage.md` |
| `ClassificationAgent` | Classifies text into a document category |
| `DocumentStore` | Tracks document status in Postgres |
| `GraphStoreService` | Upserts extracted entities/relationships into the `graph_nodes`/`graph_edges` Postgres tables — the entire reason `graph_rag` has anything to retrieve from |

`GraphStoreService` is the piece this doc previously left out completely.

### `ingest()`

Steps 1–3 (upload to S3, create the Postgres record with `document_type="document"`, update status to `processing`) are unchanged from the original version of this doc — see §2 above for the equivalent pattern.

#### Step 4: Extract text

```python
text = load_document(file_path)

if not text or not text.strip():
    raise ValueError("No text could be extracted from the document.")
```

`load_document()` dispatches to `load_pdf()`/`load_docx()`/`load_txt()`/`load_image_ocr()` by extension — full detail in `docs/load-data.md`, including the real limitations of each (e.g. `load_docx()` doesn't extract table content, `load_pdf()` silently drops image-only pages with no text layer).

#### Step 5: Classify the document

```python
document_type = self.classification_agent.classify_document(text)
```

Classifies from the **actual extracted text**, categories like `"clinical guideline"`, `"healthcare policy"`, `"patient report"`, etc. (`prompts/classification_prompt.py`'s `DOCUMENT_CATEGORIES`).

#### Step 6: Extract entities and relationships, build the graph — the missing step

```python
extraction = extract_entities_and_relationships(text)

for relationship in extraction["relationships"]:
    self.graph_store.upsert_edge(
        source_name=relationship["source"],
        target_name=relationship["target"],
        relationship=relationship["relationship"],
        file_id=file_id,
        evidence=relationship["evidence"]
    )
```

`extract_entities_and_relationships()` (`tools/entity_extraction.py`) runs spaCy: sentence segmentation, noun-chunk extraction as candidate entities, and — for every pair of entities co-occurring in the same sentence — a relationship, using the dependency parse to find a connecting verb (falling back to `"related_to"` if none is found). Returns `{"entities": [...sorted unique strings...], "relationships": [{"source", "target", "relationship", "evidence"}, ...]}`.

`GraphStoreService.upsert_edge()` upserts both endpoint nodes (deduped by normalized lowercase text, tracking mention count and which `file_id`s mentioned them) and the edge itself into Postgres. **This is what `graph_rag_agent.py` traverses at query time** — without this step running at ingestion, `graph_rag` would have nothing to retrieve. Full detail, including the documented "prototype tier, not Neptune" limitations (co-occurrence heuristic, no entity resolution/synonyms, full graph reload on every query), is in `docs/question-graph-agents-prompts.md` §4.

This step runs **before** chunking/embedding — extraction and classification both need the full, unchunked text.

#### Step 7: Chunk the text

```python
text_chunks = chunk_documents(text)
```

Standard chunking (`chunk_size=1000, chunk_overlap=150` defaults) — see `docs/rag-utils.md` for the splitter details and its reuse by `SummarizationAgent`'s map-reduce with different parameters.

#### Step 8: Create embeddings

```python
embedded_chunks = create_embeddings_for_chunks(text_chunks)
```

One `EmbeddingService.create_embedding()` call per chunk — not a batch API call, see `docs/rag-utils.md`.

#### Step 9: Bulk-index into OpenSearch

```python
self.vector_store.index_chunks(
    chunks=embedded_chunks, file_id=file_id, file_name=file_name,
    document_type=document_type, s3_uri=s3_uri,
    metadata={"source": "user_upload", "file_extension": Path(file_name).suffix.lower()},
    batch_size=500
)
```

One `helpers.bulk()` call for the whole document instead of one request per chunk — full detail (deterministic chunk IDs, `chunk_size` batching) in `docs/aws-storage.md`.

#### Step 10: Update status to `indexed`

```python
self.document_store.update_status(file_id=file_id, status="indexed", document_type=document_type)
```

### Return value

```python
return {
    "status": "indexed",
    "file_id": file_id,
    "file_name": file_name,
    "s3_uri": s3_uri,
    "document_type": document_type,
    "chunks_indexed": len(embedded_chunks),
    "entities_extracted": len(extraction["entities"]),
    "relationships_extracted": len(extraction["relationships"])
}
```

`entities_extracted` and `relationships_extracted` are new fields since this doc was first written — direct evidence, in the API response itself, that the graph-building step (Step 6) actually ran.

---

## 4. Status lifecycle

Both workflows update document status in Postgres, via `DocumentStore.update_status()`.

| Status | Meaning |
| --- | --- |
| `uploaded` | File was uploaded and the Postgres record was created |
| `processing` | The ingestion pipeline is running |
| `registered` | Structured dataset was registered in Glue **and** dual-written into Postgres |
| `indexed` | Document chunks were indexed in OpenSearch **and** its entities/relationships were upserted into the graph |
| `failed` | Ingestion failed — `error_message` is set, and `processed_at` stays `null` |

`processed_at` is set by `DocumentStore.update_status()` specifically when `status in ["registered", "indexed"]` — not on `"failed"`, which is why a failed document's `processed_at` stays `null` in `GET /documents`.

---

## 5. Difference between the two workflow files

| File | Handles | Final storage |
| --- | --- | --- |
| `structured_ingestion_workflow.py` | CSV | S3 (raw file) + Glue (Athena schema) + Postgres (metadata **and** the actual dual-written table) |
| `document_ingestion_workflow.py` | PDF / DOCX / TXT / images | S3 (raw file) + OpenSearch (chunks + embeddings) + Postgres (metadata **and** extracted graph nodes/edges) |

Both use Postgres for metadata/status tracking (`documents` table) — but that's no longer the *only* thing either workflow puts in Postgres: structured ingestion also writes the real data table there now, and document ingestion also writes the knowledge graph there. Neither workflow's storage footprint is fully captured by "S3 + one other AWS service" anymore.

---

## 6. How they're actually used from `api/routes.py`

The original version of this doc showed hand-written pseudocode with its own extension-matching logic and per-request `workflow = StructuredIngestionWorkflow()` construction. That's not how the real route works — see `docs/routers.md` for the accurate walkthrough, but in short:

- Both workflows are **module-level singletons**, constructed once at import time in `api/routes.py`, not per-request.
- The branch isn't a raw extension check — it's `detect_file_type(local_path) == "structured"` (`tools/data_loader.py`), which also handles `"document"`/`"image"`/`"unknown"` (unknowns rejected with a 400 before either workflow is ever called; images currently fall into the *document* workflow's branch, not a separate one — see `docs/load-data.md` for that specific nuance).

---

## 7. Summary

```text
structured_ingestion_workflow.py
= uploads to S3, classifies the dataset, registers it in Glue for Athena,
  AND dual-writes it into a real Postgres table for the sql route

document_ingestion_workflow.py
= uploads to S3, classifies the text, extracts entities/relationships into
  the knowledge graph, then chunks/embeds/bulk-indexes into OpenSearch for RAG

document_store_service.py
= tracks status and metadata for both workflows in Postgres (self-hosted,
  not RDS — see docs/RDS-glue.md)
```
