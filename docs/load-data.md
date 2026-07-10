These functions belong in a **tools** module (`app/backend/tools/data_loader.py`) because they perform **file-type detection and raw text/data extraction** before the result is passed to AI agents or databases. Each function has a single responsibility.


# The dispatch flow

```text
Upload arrives (api/routes.py)
        │
        ▼
  detect_file_type(file_path)
        │
  ┌─────┼──────────────┐
  ▼     ▼               ▼
"structured"  "document"      "image"/"unknown"
  │             │                  │
  ▼             ▼                  ▼
structured_ingestion_    document_ingestion_    rejected with
workflow.py               workflow.py            HTTP 400
  │                        │
  ▼                        ▼
load_csv(file_path)   load_document(file_path)
                            │
                  ┌─────────┼─────────┬──────────────┐
                  ▼         ▼         ▼              ▼
              load_pdf() load_docx() load_txt()  load_image_ocr()
              (.pdf)     (.docx)     (.txt)      (.png/.jpg/.jpeg)
```

Two things worth noting up front:

- **`detect_file_type()` only sorts files into three buckets** (`"structured"`, `"document"`, `"image"` → treated as unsupported today, see below) — the actual per-extension logic for *documents* lives one level down, inside `load_document()`.
- **`load_pdf()`, `load_docx()`, `load_txt()`, and `load_image_ocr()` are never called directly by any workflow.** Only `load_document()` calls them, based on file extension. `structured_ingestion_workflow.py` is the only workflow that calls a loader (`load_csv()`) directly, because structured files don't need the document dispatch.

---

# 1. `detect_file_type()`

```python
STRUCTURED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def detect_file_type(file_path: str) -> str:
    ext = os.path.splitext(file_path.lower())[1]

    if ext in STRUCTURED_EXTENSIONS:
        return "structured"

    if ext in DOCUMENT_EXTENSIONS:
        return "document"

    if ext in IMAGE_EXTENSIONS:
        return "image"

    return "unknown"
```

## Purpose

The very first decision made about any uploaded file: is it structured data, a document, an image, or something unsupported? Called from `api/routes.py` right after a file lands on disk.

## How it's actually used today

```python
file_type = detect_file_type(local_path)

if file_type == "unknown":
    raise HTTPException(status_code=400, detail="Unsupported file type.")
```

Only `"structured"` is checked explicitly to branch between the two ingestion workflows — everything that isn't `"structured"` (including `"image"` and `"document"`) currently falls into the same `else` branch and goes to `document_ingestion_workflow.py`. In practice this means **`"image"` is routed to the document pipeline, not handled as a separate case**, even though `detect_file_type()` distinguishes it. `load_document()` (below) is what actually dispatches `.png`/`.jpg`/`.jpeg` files to OCR.

---

# 2. `load_csv()`

```python
def load_csv(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)
```

## Purpose

The only structured-data loader. Called directly by `structured_ingestion_workflow.py` — no dispatch layer, because `.xlsx`/`.xls` aren't actually wired to a loader function despite being listed in `STRUCTURED_EXTENSIONS`. Uploading an Excel file today would be detected as `"structured"` by `detect_file_type()`, but `StructuredIngestionWorkflow.ingest()` checks the extension itself before calling `load_csv()` and raises `ValueError(f"Unsupported structured file type: {extension}")` for anything that isn't `.csv` — so it fails cleanly with that message rather than by calling `load_csv()` on a non-CSV file.

## Output

Returns a `pandas.DataFrame` — used downstream for Glue Catalog registration, the Postgres dual-write, and the `sample_rows` preview.

---

# 3. `load_document()` — the dispatcher

```python
def load_document(file_path: str) -> str:
    ext = os.path.splitext(file_path.lower())[1]

    if ext == ".pdf":
        return load_pdf(file_path)

    if ext == ".docx":
        return load_docx(file_path)

    if ext == ".txt":
        return load_txt(file_path)

    if ext in IMAGE_EXTENSIONS:
        return load_image_ocr(file_path)

    raise ValueError(f"Unsupported document type: {ext}")
```

## Purpose

The single entry point `document_ingestion_workflow.py` calls. It re-checks the extension itself (rather than trusting `detect_file_type()`'s coarser `"document"`/`"image"` split) and routes to the right extraction function. Always returns a plain `str` regardless of source format, so everything downstream (chunking, embedding, classification) works on the same type.

---

# 4. `load_pdf()`

```python
def load_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n".join(pages)
```

## Purpose

Extracts text from a PDF page by page using `pypdf`. `if text:` skips pages where `extract_text()` returns `None` or an empty string (common for scanned/image-only PDF pages with no embedded text layer) — those pages are silently dropped rather than raising an error. There is no OCR fallback for image-only PDF pages; only genuine image files (`.png`/`.jpg`/`.jpeg`) go through `load_image_ocr()`.

---

# 5. `load_docx()`

```python
def load_docx(file_path: str) -> str:
    document = Document(file_path)
    return "\n".join([p.text for p in document.paragraphs])
```

## Purpose

Loads a **Microsoft Word (.docx)** file and extracts all of its text, using the `python-docx` library.

## Step by step

```python
document = Document(file_path)
```

Opens the Word document. The object contains paragraphs, tables, headings, and formatting — but only `document.paragraphs` is used.

```python
[p.text for p in document.paragraphs]
```

A list comprehension pulling the text out of every paragraph:

```python
["Patient Name: John", "Diagnosis: Diabetes", "Medication..."]
```

```python
"\n".join(...)
```

Joins every paragraph into one newline-separated string:

```text
Patient Name: John
Diagnosis: Diabetes
Medication...
```

Note: table contents are **not** extracted — `document.paragraphs` doesn't include text inside Word tables. A `.docx` that puts patient data in a table rather than paragraph text would come back mostly empty.

---

# 6. `load_txt()`

```python
def load_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
```

## Purpose

Reads a plain text file directly. `errors="ignore"` silently drops any bytes that aren't valid UTF-8 instead of raising a `UnicodeDecodeError` — appropriate for uploaded files of unknown provenance/encoding, at the cost of possibly silently losing a few characters in a mis-encoded file.

---

# 7. `load_image_ocr()`

```python
def load_image_ocr(file_path: str) -> str:
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)
```

## Purpose

Runs OCR (via `pytesseract`, a wrapper around the Tesseract OCR engine — installed in the backend's Docker image, see the `tesseract-ocr` apt package in the `Dockerfile`) on an image file and returns whatever text it recognizes. This is the only loader whose output quality depends on image clarity/resolution rather than being a deterministic extraction.

---

# Why are these functions important?

AI models generally perform better when they receive **consistent, plain-text input** regardless of the original file format. Each loader's only job is turning one specific format into that common shape (`str` for documents, `DataFrame` for structured data) — normalization/cleaning of that text is not currently done anywhere in the pipeline (see the removed-functions note at the top).

The actual current flow:

```text
Uploaded File
        │
        ▼
detect_file_type()  →  "structured" / else
        │
   ┌────┴────┐
   ▼         ▼
load_csv()   load_document()  →  load_pdf() / load_docx() / load_txt() / load_image_ocr()
   │              │
   ▼              ▼
Glue Catalog +   Chunking → Embedding Generation → OpenSearch (bulk-indexed,
Postgres          see docs/aws-storage.md) → RAG retrieval
dual-write
(see docs/rag-utils.md)
```

These functions are intentionally simple, each with a single responsibility, which is what makes it straightforward to add a new format later (e.g. `.xlsx` actually wired up, or a cleaning step reintroduced) without touching the workflows that call them.
