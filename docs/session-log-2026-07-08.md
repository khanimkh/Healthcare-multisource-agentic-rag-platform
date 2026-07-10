

## Architecture Q&A

**Q: What ability should a user expect? When is `sql` used — Postgres? Is Postgres for document metadata? Where's Athena? What about Glue? Why no manual AWS setup for Glue/Athena/Postgres/SQL? What about classification and summarization — are results shown?**

- `sql` route queries **Postgres**, but nothing ever loads uploaded data into Postgres — structured uploads go to S3+Glue+Athena instead, and Postgres's own internal tables are deliberately excluded from what `sql` can see. Right now `sql` has nothing real to query.
- **Postgres's actual job** is application metadata — `documents`, `conversation_messages`, `graph_nodes`/`graph_edges` — and it's a **local Docker container, not AWS RDS**.
- **Glue and Athena needed zero manual console setup** — `GlueCatalog.ensure_database_exists()`/`register_csv_table()` self-provision via API calls. Confirmed live: `patients.csv` is a real registered Glue table pointing at its actual S3 location.
- Found a real gap: `ATHENA_OUTPUT_S3_URI` was still the placeholder default (`s3://your-bucket/...`) — fixed to the real bucket.
- **Classification and summarization** already render in the same chat UI as any other route (same `answer`/`route`/`sources` shape) — untested until today. Summarization (tested live): correctly resolved the uploaded policy document and produced an accurate summary. Classification (tested live): confirmed the known limitation — it classifies the *question text*, not a resolved document (got a lucky-ish right answer via lexical overlap, but `sources: []` and its own caveat text honestly disclosed the gap).

**Q: RDS instead of Postgres, or both?**
A: Both, understood as two environments (dev vs. real), switched via `POSTGRES_URL` — not simultaneous use. RDS bills continuously (unlike Glue/Athena), so held off provisioning one without explicit confirmation, same pattern as the OpenSearch domain.

**Q: What other ability can be added to this application to be more productive?**
A: Prioritized by real value vs. effort, grounded in gaps found today:

1. **Fix classification to resolve documents** (like summarization already does) — reuse `SummarizationAgent._resolve_document()`'s pattern in `ClassificationAgent`/`run_classification`. Highest value, smallest effort — the classification test above showed exactly this gap.
2. **Structured data actually reachable via `sql`** — either load uploaded CSVs into Postgres too (dual-write), or be explicit that `sql` is currently dead weight and `s3`/Athena is the real structured-query path.
3. **Token/cost tracking** — `ModelService` discards Bedrock's usage data entirely; surfacing per-question cost ties into the original design docs' "Estimated AWS service costs" goal, never implemented.
4. **Reranking for RAG** — `RAGAgent` returns raw kNN results today; a reranking pass would improve answer quality on ambiguous questions.
5. **Structured data preview in the UI** — `UploadResponse` already returns `columns`/`rows` for CSVs, just not visualized yet.
6. **Bulk/multi-file upload** — currently one file at a time.
7. **Real GraphRAG via Neptune** — documented upgrade path from the current spaCy+NetworkX prototype tier.
8. **RDS for persistence** — per the question above, whenever ready to move past local-only Postgres.

------------------
indexed vs registered — two different ingestion pipelines, by file type (document_ingestion_workflow.py vs structured_ingestion_workflow.py):

indexed = unstructured docs (PDF/TXT). Chunked, embedded, and written into OpenSearch as vectors — this is what makes them searchable via the rag route.
registered = structured docs (CSV). Loaded into the Glue Data Catalog (for Athena) and now also dual-written into a real Postgres table — this is what makes them queryable via sql. No embedding/chunking happens for these.
-------------------

## Ask Route Selection Clarification

/ask is not RAG-only. It first goes through a router agent at [app/backend/agents/router_agent.py](app/backend/agents/router_agent.py) that picks one of 6 routes per question, based on what tables and documents currently exist and the question intent, using guidance in [app/backend/prompts/router_prompt.py](app/backend/prompts/router_prompt.py).

| Route | Used for | Data source |
|---|---|---|
| rag | Questions about document content, policies, and guidelines | OpenSearch vector search over indexed (embedded) document chunks |
| sql | Aggregations and stats over structured tables | Postgres (the dual-write CSV tables and app tables) |
| s3 | Aggregations and stats over large structured datasets | Athena over S3 and Glue |
| graph_rag | Relationships between clinical concepts | NetworkX knowledge graph (spaCy-extracted entities and relations) |
| summarization | Summarize this document | Resolves the specific document, then LLM-summarizes it |
| classification | What type or category is this | Resolves the specific document, then LLM-classifies it |

So rag (indexed data) is only used when the question is actually about document content, for example: What factors increase readmission risk?

A question like average age by diagnosis gets routed to sql against Postgres, not RAG. This was verified in the last round of testing.

