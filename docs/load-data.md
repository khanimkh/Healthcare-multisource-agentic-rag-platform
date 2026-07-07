These functions belong in a **tools** or **preprocessing** module because they perform **data loading and cleaning** before the data is passed to AI agents or databases. Each function has a single responsibility.

---

# 1. `load_docx()`

```python
def load_docx(file_path: str) -> str:
	 document = Document(file_path)
	 return "\n".join([p.text for p in document.paragraphs])
```

## Purpose

Loads a **Microsoft Word (.docx)** file and extracts all of its text.

It converts a Word document into a plain text string that can later be:

- classified by an LLM
- chunked for RAG
- embedded
- summarized

---

## Input

```text
file_path: str
```

Example:

```text
reports/patient_report.docx
```

---

## Step 1

```python
document = Document(file_path)
```

Uses the `python-docx` library to open the Word document.

Think of it as:

```text
patient_report.docx
		↓
Document Object
```

The object now contains:

- paragraphs
- tables
- headings
- formatting

---

## Step 2

```python
document.paragraphs
```

Returns all paragraphs.

Example:

```text
Paragraph 1: Patient Name: John
Paragraph 2: Diagnosis: Diabetes
Paragraph 3: Medication...
```

---

## Step 3

```python
[p.text for p in document.paragraphs]
```

This is called a **list comprehension**.

It loops through every paragraph.

Equivalent to:

```python
texts = []
for paragraph in document.paragraphs:
	 texts.append(paragraph.text)
```

Result:

```python
["Patient Name: John", "Diagnosis: Diabetes", "Medication..."]
```

---

## Step 4

```python
"\n".join(...)
```

Joins every paragraph into one string.

Result:

```text
Patient Name: John
Diagnosis: Diabetes
Medication...
```

instead of:

```python
["...", "...", "..."]
```

---

## Output

Returns:

```text
str
```

---

## Workflow

```text
DOCX File
	↓
Open Document
	↓
Read Paragraphs
	↓
Extract Text
	↓
Single String
```

---

# 2. `clean_dataframe()`

```python
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
```

## Purpose

Prepares structured data (CSV, Excel, tables) before storing it in a database or sending it to an AI model.

It performs **basic preprocessing**.

---

## Step 1

```python
df = df.copy()
```

Creates a copy of the DataFrame.

Why?

Without it:

```python
clean_dataframe(df)
```

would modify the original DataFrame.

Using:

```python
copy()
```

protects the original data.

---

## Step 2

```python
df.columns = [
	 col.strip().lower().replace(" ", "_")
	 for col in df.columns
]
```

Standardizes column names.

Suppose the CSV contains:

```text
Original:
Patient Name
Age
Blood Pressure
```

After cleaning:

```text
Cleaned:
patient_name
age
blood_pressure
```


### Why standardize?

Databases and code prefer:

```text
patient_name
```

instead of:

```text
Patient Name
```

because they are easier to query and reference.

---

## Step 3

```python
df = df.drop_duplicates()
```

Removes duplicate rows.

---

# 3. `clean_text()`

```python
def clean_text(text: str) -> str:
    return " ".join(text.split())
```

## Purpose

Normalizes text before:

- classification
- chunking
- embeddings
- RAG

---

Suppose OCR extracted:

```text
Patient    Name:John

Smith
```

Many extra spaces and blank lines.

---

## Step 1

```python
text.split()
```

Without arguments,

`split()` separates text using **any whitespace**:

- spaces
- tabs
- newlines

Example:

```text
Patient    Name:John
```

becomes:

```python
["Patient", "Name:John"]
```

Notice all extra whitespace disappears.

---

## Step 2

```python
" ".join(...)
```

Joins everything back together using **a single space**.

Result:

```text
Patient Name:John
```

---

## Before

```text
Patient    Name:John

Smith
```

---

## After

```text
Patient Name:John Smith
```

---

## Workflow

```text
Messy Text
    ↓
Split into Words
    ↓
Remove Extra Whitespace
    ↓
Join with Single Spaces
    ↓
Clean Text
```

---

# Why are these preprocessing functions important?

AI models generally perform better when they receive **consistent, normalized input**. These functions improve the quality of the data before it reaches downstream components:

- `load_docx()` converts a Word document into plain text that can be processed by NLP pipelines.
- `clean_dataframe()` standardizes structured datasets by normalizing column names and removing duplicate rows, making them easier to store in databases and analyze.
- `clean_text()` removes unnecessary whitespace from text extracted from PDFs, Word documents, or OCR, resulting in cleaner input for chunking, embedding generation, and LLM classification.

In a typical document processing pipeline, the flow looks like this:

```text
Uploaded File
	│
	▼
Load Data (e.g., load_docx)
	│
	▼
Clean / Normalize (clean_dataframe or clean_text)
	│
	▼
Classification Agent
	│
	▼
Chunking
	│
	▼
Embedding Generation
	│
	▼
Storage / RAG Retrieval
```

These functions are intentionally simple because each one has **a single responsibility**, making the preprocessing pipeline easier to maintain, test, and reuse.
