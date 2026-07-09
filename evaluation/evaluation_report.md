# RAG Retrieval Evaluation Report

Not yet generated. `eval_questions.json` currently contains placeholder `relevant_chunk_ids`
(`"REPLACE_WITH_REAL_CHUNK_ID_*"`), not real ones, because no document has been ingested in
this environment yet — chunk ids only exist once `DocumentIngestionWorkflow.ingest()` has
actually indexed something into OpenSearch.

To generate a real report:

1. Upload/ingest at least one document so real chunks exist in OpenSearch.
2. Look up the resulting `chunk_id`s (`{file_id}_{chunk_index}`) and replace the placeholders
   in `eval_questions.json` with real ones, matched to real questions about that content.
3. Run:

   ```bash
   python -m evaluation.evaluate_rag
   ```

   This overwrites this file with the actual computed Precision@k / Recall@k / MRR / NDCG@k
   table for `k` in `(1, 3, 5, 10)`.
