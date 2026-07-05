# Analysis: RAG Query and Grounded Answer
Date: 2026-07-02
Story: 2026-07-02-rag-query-and-grounded-answer-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with eight data modules following a strict module-per-concern pattern. Relevant installed packages for this story: `sentence-transformers==2.7.0`, `chromadb==0.4.24` (added in Stories 7–9, now available), `anthropic==0.40.0` (installed since Story 3). The codebase provides two precise templates for the new modules: `data/sentiment.py` is the direct model for Story 11's Anthropic call, fence-stripping, and fallback constants; `data/vector_store.py` is the direct model for Story 10's module-level `_MODEL` instance, ChromaDB client pattern, and test isolation strategy. No new pip installs required for either story.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_parse_llm_response` fence-stripping helper | `data/sentiment.py:18–34` | Strips ` ```json ` and ` ``` ` fences before JSON parse, returns None on invalid schema — exact pattern Story 11 must replicate |
| `_SYSTEM_PROMPT` module-level constant | `data/sentiment.py:4–10` | Pattern for the evidence-only system prompt in `rag_answer.py` |
| `_EMPTY_INPUT_FALLBACK` / `_API_FAILURE_FALLBACK` | `data/sentiment.py:14–15` | Two separate fallback constants — Story 11 needs equivalent `_EMPTY_ANSWER` and `_ERROR_ANSWER` |
| `anthropic.Anthropic()` client instantiated inside function | `data/sentiment.py:42` | Client created on each call, not at module level — enables `patch("data.rag_answer.anthropic.Anthropic")` in tests without sys.modules tricks |
| `model="claude-haiku-4-5-20251001"` | `data/sentiment.py:44` | Exact model ID used for Story 11; must not use a different model name |
| `response.content[0].text` result extraction | `data/sentiment.py:54` | Pattern for extracting text from Anthropic response object |
| `MODULE_NAME = "all-MiniLM-L6-v2"` + `_MODEL = SentenceTransformer(MODULE_NAME)` | `data/vector_store.py:8–9` | Module-level model loading pattern — Story 10 replicates this verbatim in `rag_query.py` (does not import from `vector_store.py`) |
| `chromadb.PersistentClient(path=persist_dir)` | `data/vector_store.py:32` | Client initialised inside function using `CHROMA_PERSIST_DIR` env var; Story 10 follows the same pattern |
| `sys.modules.setdefault` pre-import injection | `tests/test_vector_store.py:6–7` | Blocks `sentence_transformers` and `chromadb` from loading at import time — Story 10 test file must use the exact same pattern |
| `patch.object(_module, "_MODEL", mock_model)` | `tests/test_vector_store.py:38` | Per-test `_MODEL` replacement pattern — Story 10 test reuses this |
| `patch("data.sentiment.anthropic.Anthropic")` | `tests/test_sentiment.py:24` | Anthropic constructor mock pattern — Story 11 test reuses at `data.rag_answer.anthropic.Anthropic` |
| `_make_llm_response` / `_mock_client` test helpers | `tests/test_sentiment.py:7–15` | Test helper factories — Story 11 test file should define the same shape of helper |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/rag_query.py` | New module | Does not exist; owns Story 10 entirely |
| `retrieve_chunks(question, collection_name, n_results)` | Public function | Entry point for Story 10; calls ChromaDB `collection.query()` |
| `collection.query(query_embeddings, n_results, include)` | ChromaDB API call | Returns dict with `ids`, `documents`, `metadatas`, `distances` — all as list-of-lists (one inner list per query vector); must index `[0]` to get results for the single query |
| `client.get_collection(name)` | ChromaDB API call | Use `get_collection` (not `get_or_create_collection`) in the query module — querying a non-existent collection should raise and be caught, not silently create an empty one |
| `_MODEL.encode([question])[0].tolist()` | Question embedding pattern | Single-question embedding — encode as a batch of one, take index 0; different from ingest which encodes a full list of texts |
| `data/rag_answer.py` | New module | Does not exist; owns Story 11 entirely |
| `answer_from_chunks(question, chunks)` | Public function | Entry point for Story 11; Anthropic call with evidence-only system prompt |
| `_EMPTY_ANSWER` | Module-level constant | `{"answer": "No relevant filings found.", "confidence_score": 0.0, "citations": []}` — returned when chunks list is empty |
| `_ERROR_ANSWER` | Module-level constant | `{"answer": "Error generating answer.", "confidence_score": 0.0, "citations": []}` — returned on API or parse failure |
| Evidence-only system prompt | Module-level string | Must explicitly instruct the model to answer only from provided chunk text and not from prior knowledge; must specify the exact JSON schema including the `citations` list with `section_name`, `company`, `filing_date`, `filing_type`, and `quote` fields |
| `confidence_score` clamping | Inline guard | Model may return values outside [0.0, 1.0]; must clamp with `max(0.0, min(1.0, raw))` before returning |
| `tests/test_rag_query.py` | New test file | Requires `sys.modules.setdefault` injection + `patch.object` per test; same structure as `test_vector_store.py` |
| `tests/test_rag_answer.py` | New test file | Same Anthropic mock structure as `test_sentiment.py`; no sys.modules injection needed |

---

## Strategic Approach

Follow `data/sentiment.py` for Story 11 and `data/vector_store.py` for Story 10 as the direct implementation templates — the patterns are proven, and the test infrastructure already handles both dependency types. `rag_query.py` is structurally identical to `vector_store.py` except that it calls `collection.query()` instead of `collection.upsert()` and accepts a question string instead of a chunks list. `rag_answer.py` is structurally identical to `sentiment.py` except the system prompt enforces evidence-only reasoning and the parsed response schema has three keys with a nested citations list. The two new modules remain fully independent from each other and from all existing modules: the caller wires `retrieve_chunks` output into `answer_from_chunks` input, but the modules do not import each other.

---

## Key Design Decisions

- **`get_collection` (not `get_or_create_collection`) in rag_query.py:** If the caller passes a collection name that does not exist, `get_collection` raises immediately — the outer `try/except` catches it and returns `[]`. Using `get_or_create_collection` would silently create an empty collection and return zero results with no error signal, masking a likely caller mistake.

- **Single-question batch encoding:** `_MODEL.encode([question])[0].tolist()` encodes the question as a batch of one and takes index 0. This matches ChromaDB's expected `query_embeddings` format (a list containing one embedding vector) without requiring a separate code path from the multi-text encode used in `vector_store.py`.

- **ChromaDB query result unpacking:** `collection.query()` returns `{"ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]]}` — all values are lists of lists (outer list = one entry per query vector). Since we always query with a single embedding, we access `result["documents"][0]`, `result["metadatas"][0]`, `result["distances"][0]` to get flat lists for the single query.

- **Anthropic client instantiated inside `answer_from_chunks`:** Follows the `sentiment.py` pattern exactly — creates `anthropic.Anthropic()` inside the function body so tests can mock the constructor with `patch("data.rag_answer.anthropic.Anthropic")`. A module-level client would require more complex mocking and would fail if `ANTHROPIC_API_KEY` is absent at import time.

- **`max_tokens=1024` for rag_answer:** The sentiment module uses 256 tokens because answers are short one-liners. The grounded answer includes an evidence-based explanation plus a citations list with verbatim quotes — 1024 tokens provides room for a full answer without truncation.

- **confidence_score clamping:** The model returns a float it self-estimates, which may drift slightly above 1.0 or below 0.0. Clamp with `max(0.0, min(1.0, raw_score))` after parsing; if the field is missing or not castable to float, treat as parse failure and return `_ERROR_ANSWER`.

- **No `_MODEL` sharing between `vector_store.py` and `rag_query.py`:** The no-cross-module-import rule means `rag_query.py` declares its own `MODEL_NAME` constant and its own `_MODEL` instance. Both are identical values but are loaded independently. This keeps each module self-contained and testable in isolation.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| ChromaDB query result list-of-lists format | High | `result["documents"]` is `[[chunk1, chunk2, ...]]` not `[chunk1, chunk2, ...]`. Indexing `[0]` is required; omitting it returns a list-of-lists that breaks the downstream schema. All mock setup in tests must mirror this format. |
| `get_collection` raises `InvalidCollectionException` for missing collections | Medium | In chromadb 0.4.x, calling `get_collection` on a non-existent name raises `chromadb.errors.InvalidCollectionException`. The outer `except Exception` catches it; tests must use a side_effect exception to verify the empty-list fallback. |
| confidence_score out of [0.0, 1.0] range | Medium | The model self-estimates confidence and may return 1.05 or -0.1 in edge cases. Clamping is required before return; missing clamping would violate the AC that states it must be between 0.0 and 1.0 inclusive. |
| citations in model response may not match the 5-key schema | Medium | If the model omits `quote` or uses different key names, `_parse_llm_response` in `rag_answer.py` must validate the citations list structure and return `_ERROR_ANSWER` on schema mismatch. |
| Module-level `_MODEL` triggers model download at import time | Medium | Same risk as `vector_store.py` — `test_rag_query.py` must inject `sys.modules.setdefault("sentence_transformers", MagicMock())` and `sys.modules.setdefault("chromadb", MagicMock())` before the first import of `data.rag_query`. |
| n_results larger than collection size | Low | ChromaDB returns fewer results than requested without raising when n_results exceeds the collection count. The function should return whatever ChromaDB returns (a shorter list), not raise or pad with empty dicts. |
| Chunks context window overflow | Low | Passing many large chunks to `answer_from_chunks` may approach the model's context limit. Not in scope for this story, but max_tokens=1024 constrains the response side. |

---

## Acceptance Criteria Coverage

### Story 10 — retrieve_chunks

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns a list of dicts from a valid question and collection | Needs work | New function; list-of-dicts pattern mirrors chunker return shape |
| Each dict contains exactly 7 keys: content, section_name, company, filing_date, filing_type, chunk_id, score | Needs work | Built by zipping `documents[0]`, `metadatas[0]`, `distances[0]` from ChromaDB query result |
| n_results=3 returns at most 3 chunks | Needs work | Passed directly to `collection.query(n_results=...)` |
| score field is a float reflecting semantic distance | Needs work | `distances[0][i]` from ChromaDB query; lower = more similar (cosine distance) |
| Empty or non-existent collection returns [] without raise | Supported pattern | Outer `try/except Exception` catches `InvalidCollectionException` |
| Any exception returns [] without raise | Supported pattern | Outer `try/except Exception` |

### Story 11 — answer_from_chunks

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns dict with exactly 3 keys | Needs work | Same schema-test pattern as all other modules |
| confidence_score is a float between 0.0 and 1.0 | Needs work | Requires clamping post-parse; no equivalent in `sentiment.py` (score derived from map) |
| citations list contains 5-key dicts | Needs work | Additional validation layer in `_parse_llm_response`; must check each citation has all 5 required keys |
| Empty chunks returns `_EMPTY_ANSWER` without raise | Needs work | Guard at function entry before Anthropic call, same as `analyze_sentiment` empty-string guard |
| API exception returns `_ERROR_ANSWER` without raise | Supported pattern | Outer `try/except Exception`, mirrors `_API_FAILURE_FALLBACK` pattern |
| Markdown fences stripped before JSON parse | Supported pattern | Verbatim copy of fence-stripping logic from `sentiment.py:18–34` |
| Evidence-only constraint in answer | Needs work | Enforced by system prompt content — verifiable only at integration level, not unit test level |
| Malformed JSON returns `_ERROR_ANSWER` without raise | Supported pattern | `_parse_llm_response` returns None on `JSONDecodeError`; caller returns `_ERROR_ANSWER` |

---

## Dependencies

- `data/rag_query.py` → `sentence_transformers==2.7.0` (installed), `chromadb==0.4.24` (installed), `CHROMA_PERSIST_DIR` env var (documented in `.env.example`) — no new installs
- `data/rag_answer.py` → `anthropic==0.40.0` (installed), `ANTHROPIC_API_KEY` env var (documented in `.env.example`) — no new installs
- `data/stock.py`, `data/screener.py`, `data/openbb_client.py`, `data/edgar_client.py`, `data/chunker.py`, `data/vector_store.py`, `data/sentiment.py` — no changes required
- `requirements.txt` — no changes needed
- `.env.example` — no changes needed
