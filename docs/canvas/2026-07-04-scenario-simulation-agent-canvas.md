# REASONS Canvas: Scenario Simulation Agent
Date: 2026-07-04
Analysis: 2026-07-04-scenario-simulation-agent-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The platform has no way to analyse the market impact of macroeconomic or geopolitical events from plain-language descriptions. Analysts must manually research affected sectors and companies without structured tooling.

**Goal:** A new module `data/scenario.py` with one public function `simulate_scenario(event_description)` that accepts a plain-language event string, calls Claude Haiku with a structured JSON prompt, and returns a 6-key dict describing directly/indirectly affected sectors, impacted companies, severity level, reasoning chain, and confidence score — never raising to the caller.

**Definition of Done:**
- [ ] Given a valid event string, when called, then it returns a dict with exactly the six keys: `directly_affected_sectors`, `indirectly_affected_sectors`, `impacted_companies`, `severity_level`, `reasoning_chain`, `confidence_score`
- [ ] Given a valid event string, when called, then `directly_affected_sectors` is a non-empty list of strings
- [ ] Given a valid event string, when called, then each entry in `impacted_companies` is a dict with at least `name`, `ticker`, and `impact_type`
- [ ] Given a valid event string, when called, then `severity_level` is one of "LOW", "MEDIUM", "HIGH", "CRITICAL"
- [ ] Given a valid event string, when called, then `reasoning_chain` is a non-empty list of strings
- [ ] Given a valid event string, when called, then `confidence_score` is a float in [0.0, 1.0]
- [ ] Given `None` as `event_description`, when called, then it returns `_EMPTY_RESULT` with `confidence_score: 0.0` and does not raise
- [ ] Given an empty string `""`, when called, then it returns `_EMPTY_RESULT` with `confidence_score: 0.0` and does not raise
- [ ] Given a whitespace-only string `"   "`, when called, then it returns `_EMPTY_RESULT` and does not raise
- [ ] Given the LLM returns confidence 1.5, when called, then the returned confidence is clamped to 1.0
- [ ] Given the LLM returns confidence -0.2, when called, then the returned confidence is clamped to 0.0
- [ ] Given the LLM returns severity `"high"` (lowercase), when called, then the returned severity is `"HIGH"`
- [ ] Given the LLM returns malformed JSON, when called, then it returns `_EMPTY_RESULT` and does not raise

---

## E — Entities

### Module Entities

| Entity | Type | Key Fields / Constants | Notes |
|--------|------|------------------------|-------|
| `scenario.py` | New Python module | — | Houses all constants and functions below; imports only `json` and `anthropic` |
| `_SYSTEM_PROMPT` | Module-level string constant | Defines LLM role as macroeconomic analyst; specifies exact 6-key JSON output schema including impacted_companies sub-schema (name, ticker, impact_type) | Embeds schema in the instruction to maximise parse success rate |
| `_EMPTY_RESULT` | Module-level dict constant | `directly_affected_sectors: []`, `indirectly_affected_sectors: []`, `impacted_companies: []`, `severity_level: "MEDIUM"`, `reasoning_chain: []`, `confidence_score: 0.0` | Returned via `.copy()` on any failure — never returned directly |
| `_VALID_SEVERITY_LEVELS` | Module-level frozenset constant | `{"LOW", "MEDIUM", "HIGH", "CRITICAL"}` | O(1) membership check after uppercase normalisation; unknown values default to "MEDIUM" |
| `_parse_llm_response(text)` | Private helper function | Input: raw LLM text string; Output: validated dict or None | Strips fences, parses JSON, validates all 6 keys, normalises severity, clamps confidence, skip-validates impacted_companies items per entry |
| `simulate_scenario(event_description)` | Public function | Input: str; Output: 6-key dict | Pre-flight guard on empty/None input; LLM call; delegates parse to `_parse_llm_response`; returns `_EMPTY_RESULT.copy()` on any failure; never raises |

---

## A — Approach

**Pattern:** Single-function LLM module with private parse helper, module-level fallback constant, and structured JSON output — same pattern as `data/rag_answer.py` for the outer shell, with per-item validation loop borrowed from `data/knowledge_graph.py` for `impacted_companies`

**Strategy:** `simulate_scenario` follows `rag_answer.py` structurally: one LLM call, a single `_EMPTY_RESULT` fallback for all failure modes, and `_parse_llm_response` returning `None` on any content failure so the caller has one place to handle all error cases. The key extension is that `_parse_llm_response` handles three nested validations: the top-level dict schema, per-item validation of `impacted_companies` with skip-invalid semantics, and severity normalisation with frozenset membership check. The `_SYSTEM_PROMPT` is the highest-leverage component — embedding the exact JSON schema (including the impacted_companies sub-schema) directly in the instruction maximises parse success rate without complicating the Python code.

**Scope In:**
- `data/scenario.py` with `simulate_scenario`, `_parse_llm_response`, `_SYSTEM_PROMPT`, `_EMPTY_RESULT`, `_VALID_SEVERITY_LEVELS`
- `tests/test_scenario.py` with 7 test classes covering all 13 acceptance criteria
- `max_tokens=1024` LLM call

**Scope Out:**
- No live news feed or web search integration
- No integration with `parallel_runner.py`
- No historical event backtesting or multi-event correlation
- No portfolio rebalancing, price lookups, or fundamentals fetch
- No changes to any existing module

---

## S — Structure

**Module path:** `Z:\claude\stock_analyzer\data\`

**New Files:**
- `data/scenario.py` — `_SYSTEM_PROMPT`, `_EMPTY_RESULT`, `_VALID_SEVERITY_LEVELS`, `_parse_llm_response`, `simulate_scenario`
- `tests/test_scenario.py` — 7 test classes, all tests Strong

**Modified Files:**
- None

**Database:**
- None — pure Python pipeline; no ORM, no migrations

---

## O — Operations

1. Create `data/scenario.py` with module-level constants only — write `_SYSTEM_PROMPT` as a multi-line string that instructs the LLM to act as a macroeconomic analyst and return a JSON object with exactly six keys; the prompt must specify the `impacted_companies` sub-schema (each item: `name`, `ticker`, `impact_type` as strings; use "N/A" for ticker if unknown) and instruct the LLM to return only the raw JSON object with no commentary. Write `_EMPTY_RESULT` as a dict with six keys at safe defaults. Write `_VALID_SEVERITY_LEVELS` as a frozenset of the four valid severity strings. Import only `json` and `anthropic`.

2. Add `_parse_llm_response(text)` to `data/scenario.py` — strip markdown fences by filtering out any lines that begin with triple backticks and rejoining the remaining lines. Call `json.loads` on the stripped text. Validate the result is a dict. Validate `directly_affected_sectors` is a list, is non-empty, and all items are non-empty strings; return `None` if the list is empty or any item is not a string. Validate `indirectly_affected_sectors` is a list (may be empty) of strings. For each entry in `impacted_companies`, check it is a dict with `name`, `ticker`, and `impact_type` all present as non-empty strings; silently skip entries that fail this check. Normalise `severity_level`: call `str(raw).upper()`, then check membership in `_VALID_SEVERITY_LEVELS`; if not in the set, use `"MEDIUM"`. Clamp `confidence_score` via `max(0.0, min(1.0, float(raw_confidence)))`. Validate `reasoning_chain` is a list, is non-empty, and all items are strings; return `None` if empty or any item is not a string. Return the assembled validated dict. Catch `json.JSONDecodeError`, `TypeError`, `ValueError`, and `KeyError` and return `None` in all cases.

3. Add `simulate_scenario(event_description)` to `data/scenario.py` — apply pre-flight guard: if `event_description is None` or `not str(event_description).strip()`, return `_EMPTY_RESULT.copy()` immediately without calling the LLM. Wrap the remainder in `try/except Exception: return _EMPTY_RESULT.copy()`. Inside the try block: instantiate `anthropic.Anthropic()`, call `client.messages.create` with `model="claude-haiku-4-5-20251001"`, `max_tokens=1024`, `system=_SYSTEM_PROMPT`, and a user message that embeds the event description string. Extract `response.content[0].text`. Pass the text to `_parse_llm_response`; if the result is `None`, return `_EMPTY_RESULT.copy()`. Otherwise return the validated dict.

4. Create `tests/test_scenario.py` — write two module-level mock helpers: `_make_llm_response(text)` returns a `MagicMock` with `.content` set to a list containing one `MagicMock` whose `.text` attribute equals the given text string; `_mock_client(response_text)` returns a `MagicMock` whose `.messages.create.return_value` equals `_make_llm_response(response_text)`. Write module-level JSON fixture strings: `_VALID_RESPONSE` (a JSON object with all 6 keys, `severity_level: "HIGH"`, `confidence_score: 0.82`, non-empty `directly_affected_sectors`, at least one valid `impacted_companies` entry, non-empty `reasoning_chain`); `_FENCED_RESPONSE` (same JSON wrapped in triple-backtick json fence); `_MALFORMED_RESPONSE` (invalid JSON string). Write 7 test classes — each decorated with `@patch("data.scenario.anthropic.Anthropic")`:

   - `TestOutputSchema`: `setUp` calls `simulate_scenario` with a valid event string against `_VALID_RESPONSE`; tests: result is a dict, has exactly 6 keys, key set equals the expected six names, `directly_affected_sectors` is a list, `impacted_companies` is a list, `confidence_score` is a float.
   - `TestHappyPath`: tests `directly_affected_sectors` is non-empty, `impacted_companies` first item has `name`/`ticker`/`impact_type` keys, `reasoning_chain` is non-empty, `severity_level` is in the valid set.
   - `TestSeverityNormalisation`: four tests using bespoke JSON responses — lowercase `"high"` → `"HIGH"`, mixed-case `"Critical"` → `"CRITICAL"`, unknown `"Severe"` → `"MEDIUM"`, and all four valid values (`"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`) accepted as-is.
   - `TestConfidenceClamping`: five tests — confidence `1.5` → `1.0`, confidence `-0.2` → `0.0`, confidence `0.0` exact, confidence `1.0` exact, integer confidence `1` (no decimal) → float `1.0`.
   - `TestFenceStripping`: two tests — JSON wrapped in triple-backtick json fence is parsed correctly and returns a non-empty `directly_affected_sectors`; plain JSON (no fence) also parses correctly.
   - `TestPreflightGuard`: six tests — `None` input returns `confidence_score: 0.0`, empty string `""` returns `confidence_score: 0.0`, whitespace `"   "` returns `confidence_score: 0.0`, none of the three raise, and `mock_cls.assert_not_called()` confirms no API call was made for each invalid input.
   - `TestLlmFailure`: four tests — malformed JSON returns `_EMPTY_RESULT` defaults, `anthropic.Anthropic()` raising an exception returns `_EMPTY_RESULT` defaults, JSON response that is a list (not a dict) returns `_EMPTY_RESULT`, empty `directly_affected_sectors` list returns `_EMPTY_RESULT`.

---

## N — Norms

- Module-per-concern: one public function per module, no cross-module imports from `data/`
- Module-level constants in UPPER_SNAKE_CASE; private helpers prefixed with underscore
- All public functions wrap the entire body in `try/except Exception` — never raise to caller
- Return dicts always use `.copy()` on the fallback constant — never return the module-level dict directly, which would expose it to mutation by callers
- LLM client instantiated inside the function body, not at module level — this allows test patching via `@patch("data.scenario.anthropic.Anthropic")`
- `_parse_llm_response` returns `None` on any parse or validation failure; the public function handles the None-to-fallback translation in one place
- Tests use `unittest.TestCase` with `@patch` for LLM mocking — no live API calls in the test suite
- Only `json` and `anthropic` imported — self-contained module

---

## S — Safeguards

- Never raise to caller — outer `try/except Exception` in `simulate_scenario` is mandatory; do not remove or narrow it
- Always use `_EMPTY_RESULT.copy()` — returning `_EMPTY_RESULT` directly exposes the module-level constant to mutation by callers
- `severity_level` must always be normalised before returning — apply `.upper()` and frozenset membership check on every code path; never return a raw LLM string
- `confidence_score` must always be clamped — apply `max(0.0, min(1.0, float(raw)))` before returning; never return a raw LLM numeric value
- `directly_affected_sectors` non-empty is a hard requirement per AC — an empty list from the LLM signals a failed parse, not a valid empty result; `_parse_llm_response` must return `None` in this case
- `reasoning_chain` non-empty is a hard requirement — same rule as `directly_affected_sectors`; an empty chain signals a failed parse
- `impacted_companies` items are validated skip-invalid — never fail the entire response because one company dict is malformed; silently drop invalid items and continue
- `isinstance(data, dict)` guard in `_parse_llm_response` is mandatory — the LLM may return a valid JSON array; this guard prevents a `TypeError` on subsequent key access
- Mock pattern `@patch("data.scenario.anthropic.Anthropic")` must patch at the module namespace — patching `anthropic.Anthropic` directly would miss the already-imported reference and risk live API calls in tests
- `_parse_llm_response` must validate each `reasoning_chain` item is a string — the LLM could return nested objects; `isinstance(item, str)` per item is required

---

## Change Log
