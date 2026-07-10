# Guide: `graphs/question_graph.py`, `agents/*.py`, `prompts/*.py`

> Updated to match the current code — covers `classification`'s document-resolution fix, `RAGAgent`'s reranking and source deduplication, the shared `tools/document_resolution.py` (used by both `SummarizationAgent` and `ClassificationAgent`), the `SchemaService` extraction (§7), and the `clean_sql_response()` fix. The Insights tab's chart explorer (`ChartAgent`/`VisualizationWorkflow`) is intentionally out of scope — see the note at the end of §4.

This guide explains the question-answering side of the platform: how a user's question turns into a routed, tool-backed, source-cited answer.

`docs/workflows.md` covers **ingestion** (files going in). This guide covers **question answering** (questions going out).

---

## 1. The big picture

```text
question_workflow.py (orchestration, gathers context)
        │
        ▼
graphs/question_graph.py (LangGraph state machine)
        │
        ▼
agents/*.py (one class per reasoning task)
        │
        ▼
prompts/*.py (builds the exact text sent to the LLM)
        │
        ▼
services/llm_service.py -> services/model_service.py -> Amazon Bedrock Runtime
```

In plain words:

```text
Prompt files   = decide WHAT text to send to the model
Agent files    = decide WHICH prompt to use, call the LLM/service, and shape the result
Graph file     = decides WHICH agent runs, in what order, and how state flows between them
```

None of the prompt files call Bedrock. None of the agent files build raw request bodies. Each layer only talks to the layer directly below it — this is the same layering documented in `docs/design-code-general-structure.md` ("AI service layering"), extended one level up to cover reasoning instead of just model access.

---

## 2. `state/state.py` — the shared state object

Every node in the graph receives a `QuestionState` and returns an updated `QuestionState`. It is a `TypedDict` with `total=False`, meaning every field is optional — a node only needs to fill in the fields it's responsible for.

```python
class QuestionState(TypedDict, total=False):
    session_id: str
    question: str
    route: str
    available_tables: List[str]
    available_documents: List[str]
    available_document_records: List[Dict[str, str]]
    schema_description: str
    conversation_context: str
    tool_answer: str
    sources: List[Dict[str, Any]]
    sql: Optional[str]
    final_answer: str
```

| Field | Set by | Read by |
| --- | --- | --- |
| `session_id`, `question` | caller (`question_workflow.py`) | every node |
| `available_tables`, `available_documents`, `conversation_context` | caller | `route_question` |
| `available_document_records` | caller (`{file_id, file_name}` per document) | `run_summarization`, to resolve which document the question refers to |
| `schema_description` | caller (Postgres schema, for `sql`) | `run_sql` |
| `route` | `route_question` | `select_route`, every tool node, `compose_final_answer` |
| `tool_answer`, `sources`, `sql` | whichever tool node ran | `compose_final_answer` |
| `final_answer` | `compose_final_answer` | the caller, after `.invoke()` returns |

---

## 3. `graphs/question_graph.py` — the state machine

### Module-level singletons

```python
router_agent = RouterAgent()
sql_agent = SQLAgent()
s3_agent = S3Agent()
rag_agent = RAGAgent()
graph_rag_agent = GraphRAGAgent()
summarization_agent = SummarizationAgent()
classification_agent = ClassificationAgent()
final_answer_agent = FinalAnswerAgent()
memory_service = MemoryService()
```

Every agent is instantiated **once** when this module is imported, not once per request. This mirrors `settings = Settings()` in `config/settings.py` — a module-level singleton for something that's expensive-ish to construct (each agent opens its own `LLMService` → `ModelService`, and some open database/AWS clients) and safe to share, since none of these classes hold per-request state.

### The graph shape

```text
                              ┌─────────────┐
                    ┌────────►│    sql      ├────┐
                    │         └─────────────┘    │
                    │         ┌─────────────┐    │
                    ├────────►│     s3      ├────┤
                    │         └─────────────┘    │
                    │         ┌─────────────┐    │
  route_question ───┼────────►│    rag      ├────┤
   (RouterAgent)     │         └─────────────┘    │
                    │         ┌─────────────┐    │      ┌───────────────┐
                    ├────────►│  graph_rag  ├────┼─────►│ final_answer  ├───► END
                    │         └─────────────┘    │      └───────────────┘
                    │         ┌─────────────┐    │
                    ├────────►│summarization├────┤
                    │         └─────────────┘    │
                    │         ┌─────────────┐    │
                    └────────►│classification├───┘
                              └─────────────┘
```

`route_question` is the single entry point. `select_route` reads `state["route"]` and LangGraph's conditional edge dispatches to exactly one of the six tool nodes. Every tool node converges back on `final_answer`, which is the single exit point before `END`.

### Node functions, one by one

**`route_question(state)`** — calls `RouterAgent.route()` with whatever context the caller supplied (`available_tables`, `available_documents`, `conversation_context`) and writes the chosen route into `state["route"]`.

**`run_sql(state)`** / **`run_s3(state)`** — both call their agent's `.answer(question=...)`, which internally generates SQL, validates it's read-only, executes it, and returns `{sql, rows}`. The node stringifies `rows` into `tool_answer` (so `FinalAnswerAgent` can read it as plain text) and keeps the raw `sql` string in `state["sql"]` for the response. `run_sql` also passes `schema_description` from state (Postgres schema, built by `question_workflow.py`); `run_s3` doesn't need this from state because `S3Agent` builds its own schema description internally by calling `AthenaService.list_tables()`.

**`run_rag(state)`** / **`run_graph_rag(state)`** — both call `.answer(question=...)`, which returns `{answer, sources}`. The node copies both straight into state.

**`run_summarization(state)`** — calls `SummarizationAgent.summarize_document(question=state["question"], available_documents=state.get("available_document_records"))`, which resolves *which* uploaded document the question refers to (see the updated `SummarizationAgent` section below) before summarizing. `sources` is set to `[result["document"]]` when a document was resolved, or `[]` if the agent fell back to summarizing the question text directly (e.g. no documents exist yet, or none matched).

**`run_classification(state)`** — calls `ClassificationAgent.classify_uploaded_document(question=state["question"], available_documents=state.get("available_document_records"))`, which resolves *which* uploaded document the question refers to (the same shared resolution step `run_summarization` uses — see the updated `ClassificationAgent`/`SummarizationAgent` sections below) before classifying its actual indexed text. `sources` is set to `[result["document"]]` when a document was resolved, or `[]` if the agent fell back to classifying the raw question text directly (e.g. "classify the readmission policy" now resolves to the real document instead of just classifying that sentence).

**`compose_final_answer(state)`** — calls `FinalAnswerAgent.compose()` with everything gathered so far, then — if `session_id` is present — persists both the user's question and the assistant's answer to `MemoryService` (Postgres + Redis, see `docs/cache_memory_service.md`). This is the only node that touches conversation memory; individual tool nodes are memory-agnostic.

**`select_route(state)`** — trivial: `return state["route"]`. This is the function LangGraph calls to decide which conditional edge to follow; it exists separately from `route_question` because LangGraph's `add_conditional_edges` wants a pure "read state, return a key" function, not the node that mutates state.

### `build_question_graph()`

Registers all seven nodes (`route_question` + six tools + `final_answer`), sets `route_question` as the entry point, wires the conditional edges using the `ROUTES` list as the key→node mapping, connects every tool node to `final_answer`, and connects `final_answer` to `END`. `graph.compile()` returns a runnable object with `.invoke(initial_state) -> final_state`.

```python
question_graph = build_question_graph()
```

Compiled once at import time — `question_workflow.py` imports this already-compiled object and calls `.invoke()` on it per request; it does not rebuild the graph on every question.

---

## 4. `agents/*.py` — one class per reasoning task

Every agent follows the same shape: an `__init__` that composes `LLMService` (and whatever else it needs), and one or more methods that build a prompt, call the LLM, and shape the result. None of them touch `boto3` or `ModelService` directly — see `docs/design-code-general-structure.md` for why that split exists.

### `router_agent.py` → `RouterAgent`

| Method | Does |
| --- | --- |
| `route(question, available_tables, available_documents, conversation_context)` | Builds the router prompt, asks the LLM for one word, lower-cases and strips it, and **falls back to `"rag"`** if the model returns anything not in `ROUTES` |

The fallback matters: a routing LLM call can hallucinate an invalid route name, and `"rag"` (general document search) is the safest default for a healthcare assistant — better to search documents and say "I don't have enough information" than to silently do nothing or crash.

### `sql_agent.py` → `SQLAgent`

| Method | Does |
| --- | --- |
| `generate_sql(question, schema_description)` | Builds the SQL prompt (dialect fixed to `"PostgreSQL"`), asks the LLM, and cleans the response via the shared `clean_sql_response()` (`utils/sql_cleanup.py`) — strips a leading ` ```sql ` fence, a trailing ` ``` `, and a stray `sql\n` language-tag prefix that a plain `.strip("\`")` doesn't catch. `ChartAgent` (`agents/chart_agent.py`, outside this graph's routing — see the scope note at the end of §4) uses the same helper for the same reason. |
| `execute(sql)` | Rejects the query via `is_read_only_sql()` (from `utils/validators.py`) before ever touching the database, then runs it through a plain SQLAlchemy `text()` execute and returns rows as a list of dicts |
| `answer(question, schema_description)` | Composes the two above into `{sql, rows}` |

Queries Postgres directly with its own `create_engine(settings.postgres_url)` — same pattern as `document_store_service.py` and `memory_service.py`, each service/agent owning the engine it needs rather than sharing a global one.

### `s3_agent.py` → `S3Agent`

Same shape as `SQLAgent`, but for Amazon Athena instead of Postgres:

| Method | Does |
| --- | --- |
| `describe_schema()` | Calls `AthenaService.list_tables()` (which in turn reuses `GlueCatalog`'s boto3 client — see `docs/RDS-glue.md`) and formats them as a bullet list |
| `generate_sql(question)` | Same as `SQLAgent.generate_sql`, but builds its own schema description and passes `dialect="Amazon Athena (Presto) SQL"` |
| `answer(question)` | Validates with the same `is_read_only_sql()` helper, then executes via `AthenaService.run_query()` (which polls Athena's async query API until it finishes) |

**Why two separate SQL-shaped agents?** `structured_ingestion_workflow.py` stores uploaded CSVs in S3 + Glue, never in Postgres — so in practice, `S3Agent`/Athena is the one that actually answers questions about *user-uploaded* structured data today. `SQLAgent`/Postgres exists for the case where structured data does live in the application database (and is kept from ever exposing the app's own internal tables — see the `INTERNAL_TABLES` filter in `question_workflow.py`, covered below). Both share `prompts/sql_prompt.py` — the same builder function, parameterized by `dialect`, rather than two near-identical prompt files.

### `rag_agent.py` → `RAGAgent`

| Method | Does |
| --- | --- |
| `retrieve(question, k=5, document_type=None)` | Embeds the question via `EmbeddingService`, calls `OpenSearchVectorStore.search_chunks()` (a kNN vector search), then passes the results through `rerank_chunks()` before returning |
| `rerank_chunks(question, chunks)` | Builds a numbered-passage prompt (`prompts/rerank_prompt.py`), asks the LLM to return a JSON array of passage indices ordered by relevance, and reorders `chunks` accordingly. Any chunk the model's response didn't mention is appended at the end, so no result is silently dropped. Skipped entirely (returns `chunks` unchanged) when there's 0 or 1 chunk — nothing to reorder |
| `_parse_rerank_order(response, chunk_count)` | Regex-extracts a `[...]` array from the LLM's response, JSON-parses it, and filters to valid in-range integers. Returns `None` on any parse failure (not a JSON array, no array found, wrong type) |
| `answer(question, k=5, document_type=None)` | Calls `retrieve()` (which now returns reranked chunks), builds the RAG prompt from them, asks the LLM, and returns `{answer, sources}` |

**Reranking failure is non-fatal by design**: if `_parse_rerank_order()` returns `None` (the model didn't respond with a clean JSON array), `rerank_chunks()` logs a warning and falls back to the original kNN-ranked order rather than raising — a reranking hiccup degrades result quality slightly, it never breaks the `rag` route.

**Source deduplication**: `answer()`'s `sources` list is built by `_deduplicate_sources(chunks)`, keyed on `file_id` (falling back to `file_name` if `file_id` is missing) — the first (i.e. highest-reranked) occurrence per unique document wins, and later chunks from the same document are dropped from the list. Without this, a document that supplied multiple chunks among the top-k results would show up multiple times in `sources` with the same filename repeated.

This is the only agent that does retrieval before generation — everything else either queries a database directly (`sql`/`s3`) or reasons over the question text alone (`summarization`, `classification`).

### `graph_rag_agent.py` → `GraphRAGAgent`

Composes `RAGAgent` for document evidence, plus two new pieces for actual graph reasoning: `tools/entity_extraction.py` (spaCy) and `services/graph_store_service.py` (Postgres + NetworkX).

**How the graph gets built (ingestion time, not part of this agent):** `document_ingestion_workflow.py` calls `tools/entity_extraction.extract_entities_and_relationships(text)` on every ingested document. That function runs spaCy's sentence segmentation and noun-chunk parser, treats each cleaned noun chunk as a candidate entity, and — for every pair of entities that co-occur in the same sentence — adds a relationship, using the dependency parse to find a connecting verb between them (falling back to `"related_to"` if none is found). The workflow then calls `GraphStoreService.upsert_edge()` for each relationship, which upserts both endpoint nodes (deduping by normalized lowercase text, tracking `mention_count` and which `file_id`s mentioned it) and the edge (deduped on `source, target, relationship`) into two Postgres tables, `graph_nodes` and `graph_edges`.

**How `GraphRAGAgent.answer()` uses it:**

| Step | Call | Purpose |
| --- | --- | --- |
| 1 | `extract_entities_and_relationships(question)` | Reuses the same spaCy extraction to pull candidate entity names out of the *question* |
| 2 | `GraphStoreService.find_related(entities, hops=2)` | Loads the full graph from Postgres into an in-memory `networkx.MultiDiGraph`, fuzzy-matches (substring, both directions) the question's entities against stored node ids, and runs `nx.ego_graph(..., undirected=True)` from each match to collect every edge within `hops` steps |
| 3 | `RAGAgent.retrieve(question, k)` | Still runs vector search for supporting document text/citations, same as before |
| 4 | `build_graph_rag_prompt(question, graph_facts, chunks)` | Combines both into one prompt — graph facts as `source --relationship--> target (from: evidence sentence)` lines, plus the RAG chunks as before |

This is a real, functional change from before: `graph_rag` and `rag` no longer return identical retrieval — `graph_rag` now has an actual traversable knowledge graph behind it, built from every document that's been ingested since this was turned on.

> **Known limitations, by design (this is the "moderate, no new AWS cost" tier, not full Neptune)**:
> - **Entity/relationship extraction is a co-occurrence heuristic, not true relation extraction.** "Two noun phrases in the same sentence, connected by whatever verb sits between them" will produce noisy edges (including ones a human wouldn't consider meaningful) alongside real ones like `metformin --treat--> diabetes`.
> - **No entity resolution/synonyms.** `"diabetes"`, `"type 2 diabetes"`, and `"diabetes mellitus"` become three separate nodes unless the fuzzy substring match in `find_related()` happens to bridge them at query time. The graph will accumulate near-duplicate nodes as more documents are ingested.
> - **`find_related()` reloads and rebuilds the entire graph from Postgres on every call.** Fine at prototype scale; would need caching (or moving to a real graph database) once `graph_nodes`/`graph_edges` grow large.
> - **This is the documented upgrade path to real Neptune** if/when it's worth the infrastructure cost — swapping `GraphStoreService` for a `NeptuneService` with the same `find_related()`-shaped interface is the natural next step, without needing to change `GraphRAGAgent.answer()`'s overall flow.

### `summarization_agent.py` → `SummarizationAgent`

Composes `LLMService` and `OpenSearchVectorStore` (to fetch a resolved document's full text).

| Method | Does |
| --- | --- |
| `summarize_document(question, available_documents, instructions=None)` | The entry point used by `question_graph.py`. Resolves which document (if any) the question refers to, fetches its full text, and summarizes it — see below. |
| `summarize(text, instructions=None)` | The actual summarization call — see map-reduce below. Still usable directly (that's the fallback path when no document resolves). |
| `_summarize_piece(text, instructions)` | One LLM call: builds the prompt via `prompts/summary_prompt.py` and generates. |

**Document resolution is shared, not private to this agent.** It used to be a private `_resolve_document()` method here; it's now `resolve_document(question, available_documents)` in `tools/document_resolution.py`, imported by both `SummarizationAgent` and `ClassificationAgent` (see below) — extracted specifically so `ClassificationAgent` didn't have to duplicate the same fuzzy-matching logic when it gained document resolution.

```text
question: "summarize the readmission policy"
available_documents: [{"file_id": "abc", "file_name": "readmission_policy.pdf"}, ...]
        │
        ▼
resolve_document() — for each candidate, splits the filename stem into words
        ("readmission_policy.pdf" -> ["readmission", "policy"]), scores what
        fraction of those words (len > 2) appear in the question text, keeps
        the best-scoring match if its score is >= 0.5, else returns None
        │
        ▼
matches "readmission" + "policy" against the question -> abc
        │
        ▼
OpenSearchVectorStore.get_document_text("abc")
        -> queries all indexed chunks for that file_id, sorted by chunk_index, joins them
        │
        ▼
summarize(full_text, instructions=question)
```

If no document resolves (score never reaches 0.5 — including when `available_documents` is empty, e.g. nothing's been ingested yet) or the resolved document has no indexed text, it falls back to summarizing the raw question text, which was the entire previous behavior — so this is a strict improvement, not a breaking change.

Passing `instructions=question` when a document *does* resolve is what makes the `instructions` parameter load-bearing: `"summarize the readmission policy in three bullet points"` resolves to the readmission policy document, and the *whole question* (including "in three bullet points") becomes the instruction guiding how the LLM summarizes it.

**Map-reduce for long documents**, replacing the old hard truncation at 8000 characters:

```text
len(text) <= MAP_REDUCE_THRESHOLD (6000 chars)?
        │
        ├─ yes -> one _summarize_piece() call, done
        │
        └─ no  -> chunk_documents() splits text into ~6000-char pieces (reusing
                  rag_utils.py's splitter, not a new chunking implementation)
                        │
                        ▼
                  _summarize_piece() on each piece ("map")
                        │
                        ▼
                  join partial summaries, one more _summarize_piece() call
                  to combine them into a single coherent summary ("reduce")
```

`prompts/summary_prompt.py`'s `build_summary_prompt()` no longer truncates text itself (`text[:8000]` was removed) — the agent guarantees every piece it hands to the prompt builder is already under the threshold, so nothing gets silently cut off anymore.

> **Known limitation**: the reduce step is a single pass — if a document is so long it produces enough partial summaries that *their combined length* exceeds `MAP_REDUCE_THRESHOLD` again, that reduce call isn't itself recursively chunked. Acceptable for realistic policy-document-sized inputs; a fully robust implementation would make `_summarize_piece`'s reduce step recursive.


### `classification_agent.py` → `ClassificationAgent`

Composes `LLMService` and `OpenSearchVectorStore` (the same "fetch a resolved document's full text" need `SummarizationAgent` has). Three methods, all funneling into the same category list (`DOCUMENT_CATEGORIES` in `prompts/classification_prompt.py`):

| Method | Input | Used by |
| --- | --- | --- |
| `classify_document(text)` | raw extracted text | `document_ingestion_workflow.py` (at upload time), `classify_uploaded_document()` (below), and as the fallback inside `classify_uploaded_document()` itself |
| `classify_structured_data(df)` | a DataFrame's column names | `structured_ingestion_workflow.py` (at upload time) |
| `classify_uploaded_document(question, available_documents=None)` | a chat question | `question_graph.py`'s `run_classification` |

`classify_uploaded_document()` mirrors `SummarizationAgent.summarize_document()`'s pattern exactly: calls the shared `resolve_document(question, available_documents)` (`tools/document_resolution.py`) to find which uploaded document the question refers to, fetches its indexed text via `OpenSearchVectorStore.get_document_text()`, and calls `classify_document()` on the *real document text* rather than the question sentence. If no document resolves (or the resolved one has no indexed text), it falls back to `classify_document(question)` — classifying the raw question text, which was the entire previous behavior for the `classification` route, so this is a strict improvement, not a breaking change. Returns `{category, document}`, where `document` is `None` on the fallback path.

This is the single home for classification in the whole project — both ingestion workflows and the question-answering graph call into it, rather than each maintaining their own category list and prompt (see the "duplicate classification logic" fix in `docs/design-code-general-structure.md`).

### `final_answer_agent.py` → `FinalAnswerAgent`

One method: `compose(question, route, tool_answer, sources=None, sql=None)`. Takes whatever the tool node produced and asks the LLM to write the actual user-facing answer, folding in citations and the generated SQL (if any) so the final response is self-explanatory rather than a raw dump of `tool_answer`. Returns `{answer, route, sources, sql}` — `question_graph.py` only reads `answer` out of this for `state["final_answer"]`, but the full dict is available if a caller wants the route/sources/sql surfaced separately (which `question_workflow.py` does, in its own return value).

### Out of scope for this doc: `chart_agent.py` → `ChartAgent`

This doc covers the `POST /ask` question-answering graph specifically. There's a second, separate agent — `ChartAgent`, composing `SQLAgent` (for its shared `execute()`/safety-check plumbing) and `LLMService` — that powers the Insights tab's "Explore your data" chart explorer (`POST /visualizations`, `GET /visualizations/suggestions`, served by `workflows/visualization_workflow.py`). It's not wired into `question_graph.py` or `RouterAgent` at all today — asking "show me a chart of X" in the main chat won't currently reach it, since there's no `chart` entry in `router_prompt.py`'s `ROUTES`. It's mentioned here only because it shares `sql_agent.py`'s `clean_sql_response()` fix (above) and reuses the same "example row in the schema description" fix described in §7.

---

## 5. `prompts/*.py` — prompt construction, isolated from reasoning logic

Each file exports:
- a `*_SYSTEM_PROMPT` constant — the fixed instruction sent as the system prompt on every call for that task
- a `build_*_prompt(...)` function — assembles the per-call user prompt from arguments, returns a plain string

No prompt file imports any service or agent — they are pure string-building functions, which is what makes them independently testable and reusable (e.g. `sql_prompt.py` is reused by both `SQLAgent` and `S3Agent`).

| File | System prompt's role | Builder function | Key parameters |
| --- | --- | --- | --- |
| `router_prompt.py` | Constrains the model to return exactly one of `ROUTES` | `build_router_prompt` | `available_tables`, `available_documents`, `conversation_context` — each defaults to `"none"` in the rendered prompt if not supplied |
| `sql_prompt.py` | Constrains the model to a single read-only SELECT, no markdown | `build_sql_prompt` | `dialect` (default `"PostgreSQL"`) — the same builder serves both `SQLAgent` (Postgres) and `S3Agent` (Athena/Presto) |
| `rag_prompt.py` | Forces "answer only from context, say so if you don't know, cite sources" | `build_rag_prompt` | `chunks` — a list of `{file_name, text, ...}` dicts, rendered as `[Source: ...]` blocks |
| `graph_rag_prompt.py` | Forces reasoning from graph facts + document evidence only | `build_graph_rag_prompt` | `graph_facts` — a list of `{source, target, relationship, evidence}` triples from `GraphStoreService.find_related()`; `chunks` — same shape as `rag_prompt.py` |
| `summary_prompt.py` | Sets tone/audience (business + clinical readers), forbids adding unsourced info | `build_summary_prompt` | `instructions` — optional override of the default task line; no longer truncates `text` (the agent guarantees a safe size before calling this) |
| `classification_prompt.py` | "Return only the category name" | `build_document_classification_prompt`, `build_structured_classification_prompt` | Also exports `DOCUMENT_CATEGORIES` — the single shared category list |
| `final_answer_prompt.py` | Requires sources + limitations, forbids direct medical advice | `build_final_answer_prompt` | `sources`, `sql` — both rendered as "none" when absent so the prompt is well-formed either way |

### Why `ROUTES` lives in `router_prompt.py`, not the agent

```python
ROUTES: List[str] = ["sql", "s3", "rag", "graph_rag", "summarization", "classification"]
```

`router_prompt.py` is the single source of truth for valid route names. `RouterAgent` imports it to validate the model's response; `question_graph.py` imports the *values* implicitly by using the same six strings as node names and conditional-edge keys. Adding a new route means: add it to this list, add the routing rule sentence in `build_router_prompt`, add a node + edge in `question_graph.py` — three edits, one canonical list.

---

## 6. Route → agent → prompt → node, at a glance

| Route | Agent | Prompt file(s) | Graph node |
| --- | --- | --- | --- |
| `sql` | `SQLAgent` | `sql_prompt.py` (`dialect="PostgreSQL"`) | `run_sql` |
| `s3` | `S3Agent` | `sql_prompt.py` (`dialect="Amazon Athena (Presto) SQL"`) | `run_s3` |
| `rag` | `RAGAgent` | `rag_prompt.py` | `run_rag` |
| `graph_rag` | `GraphRAGAgent` (composes `RAGAgent` + `GraphStoreService`) | `graph_rag_prompt.py` | `run_graph_rag` |
| `summarization` | `SummarizationAgent` | `summary_prompt.py` | `run_summarization` |
| `classification` | `ClassificationAgent` | `classification_prompt.py` | `run_classification` |
| *(all routes converge)* | `FinalAnswerAgent` | `final_answer_prompt.py` | `compose_final_answer` |
| *(routing itself)* | `RouterAgent` | `router_prompt.py` | `route_question` |

---

## 7. How `question_workflow.py` feeds this graph

`QuestionWorkflow.ask(question, session_id)` builds the `initial_state` this whole system runs on. The Postgres-introspection piece now lives in a separate `SchemaService` (`services/schema_service.py`) that `QuestionWorkflow` composes, rather than `QuestionWorkflow` owning its own SQLAlchemy engine and introspection methods directly — `SchemaService` is also reused by `VisualizationWorkflow` for the chart explorer (see the scope note in §4), which is why it was pulled out on its own:

```text
SchemaService.describe_tables() (minus INTERNAL_TABLES: documents,
        conversation_messages, graph_nodes, graph_edges)
        -> available_tables (partial)

SchemaService.format_description()
        -> schema_description — one "- table(col1, col2, ...)" line per table,
           PLUS one real example row per table (e.g. {"patient_id": 1, "age": 45,
           "diagnosis": "diabetes", "readmitted": "no"}), so the SQL-generating
           LLM sees actual value formats instead of guessing. This was added
           after a real bug: without it, the model generated `readmitted = true`
           against a column that actually stores the text 'yes'/'no', which
           Postgres rejected. `sql_prompt.py`'s system prompt now explicitly
           tells the model to match the example row's types/formats.

AthenaService.list_tables()
        -> available_tables (rest)

DocumentStore.list_indexed_document_records()
        -> available_documents (file names only, for the router prompt)
        -> available_document_records ({file_id, file_name} pairs, for
           summarization AND classification resolution — see §4)

MemoryService.get_recent_messages(session_id)
        -> conversation_context
```

`graph_nodes`/`graph_edges` were added to `INTERNAL_TABLES` alongside the `SchemaService` extraction — before that fix, the `sql` route could see the knowledge-graph's own storage tables as if they were queryable user data, which they aren't meant to be.

Then `question_graph.invoke(initial_state)` runs everything described above, and `QuestionWorkflow` extracts `{answer, route, sql, sources}` from the final state for the API layer (`POST /ask`) to return.
