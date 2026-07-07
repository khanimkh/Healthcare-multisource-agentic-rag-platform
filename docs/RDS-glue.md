## Glue metadata answers this:

```text
What datasets/tables exist for Athena to query?
Where is the CSV in S3?
What are the columns and data types?
```

Example Glue table:

```text
table_name: patients
location: s3://bucket/uploads/file_id/patients.csv
columns: patient_id, age, diagnosis
format: CSV
```

Glue is mainly for **data discovery + Athena SQL**.

---

## RDS metadata answers this:

```text
Who uploaded this file?
What is the processing status?
Did ingestion fail?
Which user owns it?
When was it processed?
Can the user delete it?
Which OpenSearch chunks belong to it?
Which Glue table belongs to it?
```

Example RDS `documents` row:

```text
file_id: abc123
file_name: patients.csv
s3_uri: s3://bucket/uploads/abc123/patients.csv
status: registered
owner_user_id: user_01
glue_table: patients
uploaded_at: 2026-07-06
error_message: null
```

RDS is your **application control database**.

---

## Simple comparison

| Question | Glue | RDS |
| --- | --- | --- |
| What columns does `patients.csv` have? | ✅ Yes | Usually no |
| Can Athena query this file? | ✅ Yes | No |
| Who uploaded the file? | No | ✅ Yes |
| Is ingestion processing, failed, or done? | No | ✅ Yes |
| Which user can access it? | No | ✅ Yes |
| Store chat history / jobs / audit logs? | No | ✅ Yes |
| Store table schema for Athena? | ✅ Yes | No |

---

So you still need RDS because Glue is not designed to manage your application workflow.

Best design:

```text
S3 = actual files
Glue = table/schema metadata for Athena
RDS = app metadata, file lifecycle, users, jobs, status, permissions
OpenSearch = chunks + embeddings
```

In RDS, you can store a reference to Glue:

```text
documents
- file_id
- file_name
- s3_uri
- file_type
- status
- glue_database
- glue_table
- uploaded_at
- processed_at
- error_message
```

That connects the application record to the Glue table.
