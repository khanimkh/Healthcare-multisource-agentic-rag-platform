## `cache_service.py` -> generic cache layer

Its responsibility is to **talk to Redis** and nothing else. It owns the raw `redis.Redis` client so that no other file in the project needs to create one.

It knows **nothing** about conversations, sessions, or any specific domain -- it only stores and retrieves JSON values and JSON lists by key.

```text
Any value
	│
	▼
CacheService
────────────────────────
set_json / get_json          -> single value by key
push_json / get_list_json    -> append-only list by key (capped length)
delete                       -> remove a key
────────────────────────
	│
	▼
Redis
```

So you can say:

> **cache_service.py is a generic, domain-agnostic wrapper around Redis.**

### Function abstract

| Function | Purpose |
| --- | --- |
| `set_json(key, value, ttl=None)` | Store any JSON-serializable value under a key, with an optional expiry |
| `get_json(key)` | Retrieve and decode a value, or `None` if the key doesn't exist |
| `delete(key)` | Remove a key |
| `push_json(key, value, max_length=None)` | Append a value to a Redis list, trimming it to `max_length` if given |
| `get_list_json(key)` | Retrieve and decode every item currently in a list key |

---

## `memory_service.py` -> conversation memory layer

Its responsibility is to **remember conversations**. It composes `CacheService` for fast, short-term recall and owns its own Postgres table for the durable, full history.

```text
User turn
	│
	▼
MemoryService
────────────────────────
Postgres (conversation_messages table)
	-> durable, full history, survives restarts

CacheService / Redis (one list per session_id)
	-> fast cache of the most recent N turns
	-> read first; only falls back to Postgres on a cache miss
────────────────────────
```

So you can say:

> **memory_service.py persists and retrieves per-session chat turns, using Postgres for durability and CacheService (Redis) for low-latency recent-turn lookups.**

### Data model: `ConversationMessage`

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | Integer (PK) | Auto-incrementing row id |
| `session_id` | String | Groups messages belonging to one conversation |
| `role` | String | `"user"` or `"assistant"` |
| `content` | Text | The message text |
| `created_at` | DateTime | UTC timestamp the message was stored |

### Function abstract

| Function | Reads/Writes | Purpose |
| --- | --- | --- |
| `add_message(session_id, role, content)` | Postgres insert + cache push | Append one turn to durable history and the recent-turns cache |
| `get_recent_messages(session_id)` | Cache read (Postgres fallback) | Fast retrieval of the last N turns for prompting; rebuilds the cache from Postgres on a miss |
| `get_history(session_id, limit=50)` | Postgres read | The most recent `limit` turns for a session, returned oldest -> newest |
| `clear_session(session_id)` | Cache delete | Evict the cached recent turns only; Postgres history is untouched |
| `delete_session_history(session_id)` | Postgres delete + cache delete | Permanently forget a session's entire history |

---

## Why two files instead of one

This mirrors the same layering used for the Bedrock services (`model_service.py` owns the raw client; `embedding_service.py`, `llm_service.py`, and `agents/classification_agent.py` compose it): exactly one file owns the raw Redis client, and the domain-specific file builds on top of it instead of duplicating connection logic.

```text
memory_service.py (conversation-specific)
	│
	▼
cache_service.py (generic Redis wrapper, owns the client)
	│
	▼
Redis
```

The benefit: `CacheService` stays reusable for anything that needs simple caching (for example, caching upload metadata in `routes.py`), without dragging in Postgres or conversation-specific logic. If another domain later needs its own durable-plus-cached pattern, it composes `CacheService` the same way `MemoryService` does, instead of opening a second Redis connection.
