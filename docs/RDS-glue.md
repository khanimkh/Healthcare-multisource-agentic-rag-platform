> **Terminology fix**: this doc originally said "RDS" throughout. This project does not use AWS RDS — `settings.postgres_url` points at a self-hosted Postgres container (`postgres:16-alpine` in `docker-compose.yml`), the same one every other doc in this repo (`cache_memory_service.md`, `question-graph-agents-prompts.md`, etc.) just calls "Postgres." The conceptual split described below (discovery/schema metadata vs. application control metadata) is still the right way to think about Glue vs. Postgres — only the label was wrong.

## Glue metadata answers this:

```text
What datasets/tables exist for Athena to query?
Where is the CSV in S3?
What are the columns and data types?
```

Example Glue table, as actually registered by `GlueCatalog.register_csv_table()` (`services/glue_catalog_service.py`):

```text
table_name: patients                              (normalize_table_name(dataset_name) —
                                                     lowercased, non-alphanumerics -> "_")
location: s3://bucket/uploads/{file_id}/patients.csv
columns: patient_id (bigint), age (bigint), diagnosis (string), ...
                                                    (inferred from df.dtypes via
                                                     _map_dtype_to_glue(), column
                                                     names also normalized)
format: CSV (OpenCSVSerde, comma-separated, 1 header line skipped)
```

`register_csv_table()` calls `ensure_database_exists()` first (creates the Glue database if it's missing — this project hit that exact gap early on: Athena queries failed until this existence check was added), then either creates or updates the table (`get_table` + `update_table`, falling back to `create_table` on `EntityNotFoundException`) — so re-uploading a file with the same name refreshes its Glue schema instead of erroring.

`AthenaService.list_tables()` is just `GlueCatalog`'s own paginated `get_tables` call reused — `AthenaService` doesn't talk to Glue independently, it composes `GlueCatalog` for schema discovery and only owns its own `boto3` Athena client for actually running queries (`run_query()`, which polls `get_query_execution` until `SUCCEEDED`/`FAILED`/`CANCELLED` or a timeout).

Glue is mainly for **data discovery + Athena SQL** — this is what the `s3` route (`S3Agent`) queries against, not Postgres.

---

## Postgres (`documents` table) answers this:

```text
What is the processing status?
Did ingestion fail, and why?
When was it uploaded / processed?
Which category was it classified as?
Should it be included in RAG/summarization/classification resolution?
```

The actual columns, from `DocumentRecord` in `services/document_store_service.py` — narrower than what this doc originally claimed:

```text
documents
- file_id          (primary key, UUID string)
- file_name
- s3_uri
- document_type    (nullable — the classified category, e.g. "clinical guideline")
- status           ("uploaded" -> "processing" -> "indexed"/"registered", or "failed")
- uploaded_at
- processed_at     (nullable — set only once status becomes "indexed"/"registered")
- error_message    (nullable — set only on failure)
```

Two things the original version of this doc got wrong, worth calling out explicitly:

- **There is no `owner_user_id` column, and no user/ownership concept anywhere in this project.** There's no auth system — every document is visible to every caller. If per-user access control is ever added, this table is where an `owner_user_id` column would need to go, but it doesn't exist today.
- **There is no `glue_table`/`glue_database` column, and the Glue table name is not persisted anywhere.** `StructuredIngestionWorkflow.ingest_csv()` computes `table_name` from `GlueCatalog.register_csv_table()` and returns it once in the `/upload` API response (`UploadResponse.glue_table`), but never passes it to `document_store.create_document()` or `update_status()`. So while a human reading the API response can see which Glue table a given upload created, **that link isn't queryable from the `documents` table afterward** — recovering it means re-deriving the table name from the file name via `normalize_table_name()` and hoping nothing renamed it. If that link needs to be durable (e.g. for the delete flow, which today only cleans up S3 + OpenSearch, never the Glue table or the Postgres dual-write table — see the `note` field in `DELETE /documents/{file_id}`'s response), `glue_table` would need to actually be added as a column and populated in `structured_ingestion_workflow.py`.

---

## Simple comparison

| Question | Glue | Postgres (`documents`) |
| --- | --- | --- |
| What columns does `patients.csv` have? | ✅ Yes | No |
| Can Athena query this file? | ✅ Yes | No |
| Is ingestion processing, failed, or done? | No | ✅ Yes (`status`) |
| What category was this document classified as? | No | ✅ Yes (`document_type`) |
| When was it uploaded / finished processing? | No | ✅ Yes (`uploaded_at`/`processed_at`) |
| Which Glue table does this document's row correspond to? | — | ❌ Not stored (see above) |
| Which user uploaded/owns it? | No | ❌ Not stored — no user model exists |

---

So you still need Postgres because Glue is not designed to manage your application workflow.

Actual design in this project:

```text
S3                = actual files (AWSStorage, docs/rag-utils.md)
Glue              = table/schema metadata for Athena (GlueCatalog, above)
Postgres           = app metadata/file lifecycle (documents table, above)
                     + dual-written structured data itself
                     (RelationalDataStore, docs/rag-utils.md's sibling —
                      see structured_ingestion_workflow.py)
OpenSearch        = chunks + embeddings (docs/aws-storage.md)
```

The one addition since this doc was first written: uploaded CSVs are now **dual-written** into Postgres as real queryable tables too (via `RelationalDataStore.load_dataframe()`, normalized through the same `normalize_table_name()` Glue uses) — not just registered in Glue for Athena. That's what makes the `sql` route (`SQLAgent`, Postgres) actually see user-uploaded structured data today, alongside the `s3` route (`S3Agent`, Athena) which was previously the only way to query it.
