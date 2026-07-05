# Analysis: Knowledge Graph Construction
Date: 2026-07-02
Story: 2026-07-02-knowledge-graph-construction-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with ten data modules at `Z:\claude\stock_analyzer\data\`, all following a strict module-per-concern pattern. Installed LLM client: `anthropic==0.40.0`. This story requires no new dependencies — it follows the exact same Anthropic call pattern established in `data/sentiment.py` (Story 4) and extended in `data/rag_answer.py` (Story 11). The single key structural difference from all prior LLM modules is that the response schema is a JSON **array** of objects rather than a single JSON object, and `_parse_llm_response` must perform per-item validation with skip-on-failure semantics rather than nil-on-any-failure.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_parse_llm_response` fence-stripping helper | `data/sentiment.py:18–34` | Strips ` ```json ` and ` ``` ` fences before JSON parse, returns None on invalid schema — base pattern for Story 12 |
| `_SYSTEM_PROMPT` module-level constant | `data/sentiment.py:4–10` | Pattern for the extraction-agent system prompt in `knowledge_graph.py` |
| `_EMPTY_INPUT_FALLBACK` / `_API_FAILURE_FALLBACK` | `data/sentiment.py:14–15` | Named fallback constants — Story 12 uses a single `[]` instead of two named dicts (no semantic distinction between "no text" and "error") |
| `anthropic.Anthropic()` client inside function body | `data/sentiment.py:42` | Client created per call — enables `patch("data.knowledge_graph.anthropic.Anthropic")` without sys.modules tricks |
| `model="claude-haiku-4-5-20251001"` | `data/sentiment.py:44` | Exact model ID for Story 12 |
| `response.content[0].text` result extraction | `data/sentiment.py:54` | Pattern for reading the text from the Anthropic response object |
| `confidence_score` clamping with `max/min` | `data/rag_answer.py:42` | Clamps float to [0.0, 1.0] — exact same logic needed per triple in `knowledge_graph.py` |
| Per-item list validation loop | `data/rag_answer.py:49–53` | Iterates citations list and returns None on any invalid item — Story 12 adapts this to skip-invalid rather than nil-on-invalid |
| `_make_llm_response` / `_mock_client` helpers | `tests/test_sentiment.py:7–15` | Test helper factories — Story 12 test reuses the identical shape |
| `patch("data.rag_answer.anthropic.Anthropic")` | `tests/test_rag_answer.py` | Anthropic constructor mock pattern at module path — Story 12 uses `data.knowledge_graph.anthropic.Anthropic` |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/knowledge_graph.py` | New module | Does not exist; owns Story 12 entirely |
| `extract_relationships(text)` | Public function | Entry point — LLM call + array parse + per-triple validation |
| Knowledge graph extraction system prompt | Module-level string | Must instruct the model to return a JSON array (not object) of triples; explicitly name the four required keys per triple |
| `_parse_llm_response` (array variant) | Private helper | Parses a JSON array; clamps confidence per item; skips invalid items; returns the valid subset or [] |
| `tests/test_knowledge_graph.py` | New test file | Anthropic client mocked; no sys.modules injection needed |

---

## Strategic Approach

`data/knowledge_graph.py` is structurally identical to `data/sentiment.py` at the module level — same `_SYSTEM_PROMPT` constant, same `anthropic.Anthropic()` instantiation inside the function, same `_parse_llm_response` fence-stripping helper, same outer `try/except` boundary. The single meaningful divergence is that the LLM is asked to return a JSON **array** of triple objects rather than a single JSON object, which shifts `_parse_llm_response` from "validate one object and return it or None" to "validate each item in a list, collect the valid ones, and return the subset." This skip-invalid behaviour is a deliberate upgrade from `rag_answer.py`'s nil-on-any-failure strategy: partial extraction of relationships is always more useful than returning nothing because one triple failed schema validation. The test file follows `test_rag_answer.py`'s style — plain pytest functions with `@patch` decorators, not the `unittest.TestCase` class used in `test_sentiment.py`.

---

## Key Design Decisions

- **JSON array at the top level, not a wrapper object:** The model returns `[{...}, {...}]` directly. There is no outer wrapper key like `"relationships": [...]`. This keeps the system prompt simpler and the parse path shorter — `json.loads` returns a list directly, no dict access needed before iterating.

- **Single `[]` fallback for all failure modes:** Unlike `rag_answer.py` which has `_EMPTY_ANSWER` vs `_ERROR_ANSWER` (semantically distinct for callers), `knowledge_graph.py` returns `[]` for all failure cases — empty input, API exception, malformed JSON, zero valid triples. The distinction between "no text" and "API error" is not meaningful to a knowledge graph builder; both mean "no triples." This reduces constant clutter.

- **Skip-invalid rather than nil-on-invalid in `_parse_llm_response`:** If the model returns 3 triples and one is missing `confidence`, returning `None` (and therefore `[]`) loses the 2 valid triples. Skipping invalid items and returning the rest is strictly better — the story explicitly calls this out as the required behaviour. This is the key design difference from `rag_answer.py`'s citation validation.

- **`confidence` clamped per triple:** Same `max(0.0, min(1.0, float(raw)))` pattern as `rag_answer.py`. Applied inside the per-item loop before the item is appended to the valid-triples list.

- **`max_tokens=512`:** Sentiment uses 256 (one short object). RAG answer uses 1024 (multi-paragraph answer plus citations). Knowledge graph extraction can produce a variable number of triples but they are compact; 512 tokens covers 5–8 triples comfortably without over-provisioning.

- **No cross-module import:** `knowledge_graph.py` does not import from `sentiment.py` or `rag_answer.py`. The fence-stripping logic and clamping pattern are duplicated — this is intentional per the no-cross-module-import rule.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Model returns a JSON object instead of a bare array | High | If the model wraps the array (e.g. `{"relationships": [...]}`) instead of returning a bare array, `json.loads` succeeds but the result is a dict, not a list — `isinstance(data, list)` check must guard this before iterating |
| Model returns an empty array `[]` for text with no relationships | Medium | Valid response; must return `[]` without treating it as a parse failure. The empty-array case is normal and must not be confused with an error |
| `confidence` field missing or non-numeric in a triple | Medium | The skip-invalid logic must catch `TypeError`/`ValueError` from `float(raw)` per item without propagating — use a per-item inner try/except or conditional |
| `source`, `relation`, or `target` is an empty string | Medium | Validation must explicitly check that all three string fields are non-empty after stripping — the model may return `""` for entities it cannot identify, producing a useless triple |
| Partial extraction masks total model confusion | Low | If the model returns 5 triples and all 5 are invalid, `[]` is returned — same as the error case. The caller cannot distinguish "no relationships in text" from "model output entirely invalid." Acceptable; out of scope to distinguish |
| `max_tokens` overflow for dense multi-entity text | Low | A passage with 20+ entities could exceed 512 tokens; the outer `try/except` catches any resulting parse failure and returns `[]` |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| NVIDIA→TSMC triple extracted from supply-chain sentence | Needs work | New function; validated by mocked happy-path test using a fixture response containing the expected triple values |
| Each dict has exactly four keys: source, relation, target, confidence | Needs work | `_parse_llm_response` validates per-item; schema test covers this |
| confidence is a float between 0.0 and 1.0 | Needs work | Clamping with `max(0.0, min(1.0, float(raw)))` required per triple in the parse loop |
| Empty string returns `[]` without calling API | Supported pattern | Same empty-guard as `analyze_sentiment` and `answer_from_chunks`; `mock_cls.assert_not_called()` verifies no side effect |
| API exception returns `[]` without raising | Supported pattern | Outer `try/except Exception` → `return []`; same as all existing LLM modules |
| Fenced response parsed correctly | Supported pattern | Verbatim fence-stripping logic from `sentiment.py:18–23`; proven pattern across all LLM modules in the pipeline |
| Invalid triple (missing confidence) skipped, rest returned | Needs work | New behaviour not present in any existing module; per-item validation with continue-on-invalid replaces nil-on-any-invalid |
| No-relationship sentence returns `[]` | Supported pattern | Model returns `[]`; `json.loads` returns an empty list; `_parse_llm_response` returns `[]`; no special handling needed |

---

## Dependencies

- `data/knowledge_graph.py` → `anthropic==0.40.0` (installed), `ANTHROPIC_API_KEY` env var (documented in `.env.example`) — no new installs
- All existing modules unchanged — no modifications required
- `requirements.txt` — no changes needed
- `.env.example` — no changes needed
