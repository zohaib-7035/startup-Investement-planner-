# Analysis: Scenario Simulation Agent
Date: 2026-07-04
Story: 2026-07-04-scenario-simulation-agent-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with 23 modules under `data/`, each following module-per-concern pattern. The two closest existing parallels are `data/knowledge_graph.py` (LLM call with JSON list output, skip-invalid items per entry, module-level `_SYSTEM_PROMPT`) and `data/rag_answer.py` (LLM call with JSON dict output, `confidence_score` clamping, markdown fence stripping, `_EMPTY_RESULT`/`_ERROR_RESULT` distinction). The scenario module combines both: it returns a dict (like `rag_answer.py`) containing lists (like `knowledge_graph.py`). No new packages required — `anthropic` is already installed.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `_SYSTEM_PROMPT` module-level constant | `data/knowledge_graph.py`, `data/rag_answer.py` | Defines LLM role and exact JSON schema in a single string; scenario.py must define its own for the 6-key output schema |
| `_parse_llm_response(text)` private helper | `data/knowledge_graph.py`, `data/rag_answer.py` | Strips markdown fences, calls json.loads, validates schema, returns parsed data or None/[] on failure; scenario.py follows this pattern |
| Markdown fence stripping | `data/knowledge_graph.py:22-25`, `data/rag_answer.py:27-30` | startswith triple-backtick check, filter fence lines, rejoin; exact same logic reused |
| `confidence_score` clamping | `data/rag_answer.py:42-44`, `data/knowledge_graph.py:48` | max(0.0, min(1.0, float(raw))) — identical pattern reused |
| Skip-invalid per list item | `data/knowledge_graph.py:34-56` | Iterates list, validates required keys per item, silently skips malformed entries; scenario.py uses this for `impacted_companies` |
| `_EMPTY_RESULT` / `_ERROR_ANSWER` fallback constants | `data/rag_answer.py:20-21` | scenario.py uses a single `_EMPTY_RESULT` for both input-invalid and LLM-error cases (story does not require distinguishing them) |
| `anthropic.Anthropic()` inside function body | `data/knowledge_graph.py:65`, `data/rag_answer.py:77` | Client instantiated on each call, not at module level; test mocking patches `data.module_name.anthropic.Anthropic` |
| `@patch("data.module.anthropic.Anthropic")` mock pattern | `tests/test_knowledge_graph.py:54` | Class-level @patch + `_make_llm_response(text)` factory returning MagicMock with `.content[0].text = text`; scenario tests follow this |
| `model="claude-haiku-4-5-20251001"` | `data/knowledge_graph.py:68`, `data/rag_answer.py:80` | Consistent model across all LLM modules; scenario.py uses the same |
| `_VALID_ACTIONS = frozenset(...)` | `data/meta_agent.py:10` | Frozenset for O(1) membership test; scenario.py uses `_VALID_SEVERITY_LEVELS = frozenset({"LOW","MEDIUM","HIGH","CRITICAL"})` for the same purpose |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `data/scenario.py` | New Python module | Does not exist; to be created |
| `simulate_scenario(event_description)` | Public function | Returns 6-key dict; never raises |
| `_SYSTEM_PROMPT` | Module-level string constant | Defines LLM as macroeconomic analyst; specifies exact 6-key JSON schema including impacted_companies sub-schema with name/ticker/impact_type |
| `_EMPTY_RESULT` | Module-level dict constant | Six keys with safe defaults: lists empty, severity_level "MEDIUM", confidence_score 0.0; returned via .copy() |
| `_VALID_SEVERITY_LEVELS` | Module-level frozenset constant | frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"}) — validates and normalises severity_level from LLM |
| `_parse_llm_response(text)` | Private helper | Strips fences, parses JSON, validates all 6 keys, normalises severity_level, clamps confidence_score, validates impacted_companies items; returns dict or None on failure |
| `tests/test_scenario.py` | New test file | Uses unittest.TestCase + @patch("data.scenario.anthropic.Anthropic"); target: all tests Strong |

---

## Strategic Approach

`simulate_scenario` follows `rag_answer.py` structurally (single LLM call returning a dict, `_EMPTY_RESULT` fallback, `_parse_llm_response` returns `None` on failure) but borrows the per-item validation loop from `knowledge_graph.py` for the `impacted_companies` list. The `_SYSTEM_PROMPT` is the most important implementation decision — it must instruct the LLM to return a JSON object with exactly six keys and embed the sub-schema for `impacted_companies` inline. An outer `try/except Exception` wraps the entire function body; `_parse_llm_response` handles all LLM content failures internally, returning `None` which triggers `_EMPTY_RESULT.copy()` in the caller.

---

## Key Design Decisions

- **Single `_EMPTY_RESULT` for all failure modes** — unlike `rag_answer.py`'s two constants, scenario.py uses one. The story does not require distinguishing no-input from LLM-error in the output.
- **`_VALID_SEVERITY_LEVELS` frozenset** — after parsing, `severity_level` is uppercased via `str(raw).upper()` and checked against the frozenset; any unknown value defaults to `"MEDIUM"` rather than failing the whole response. Prevents discarding a valid 5-field result because the LLM used "Moderate" or "Severe".
- **`impacted_companies` items validated skip-invalid** — each dict must have `name`, `ticker`, and `impact_type` as non-empty strings; invalid items silently dropped. Matches `knowledge_graph.py` pattern.
- **`directly_affected_sectors` validated as non-empty** — story AC states it must be non-empty; if LLM returns empty list, `_parse_llm_response` returns `None` and caller returns `_EMPTY_RESULT`.
- **`reasoning_chain` validated as non-empty list of strings** — same strictness; empty chain signals parse failure.
- **`max_tokens=1024`** — 6-key output with nested lists is more verbose than knowledge_graph's 512; matches `rag_answer.py`.
- **No imports from other `data/` modules** — scenario.py is self-contained; only `json` and `anthropic` imported.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| LLM returns `severity_level` as "Moderate" or "Severe" (not in valid set) | Medium | Normalise to uppercase, check frozenset, default to "MEDIUM" — not a failure; test explicitly |
| `directly_affected_sectors` is empty list from LLM | Medium | Story AC requires non-empty; _parse_llm_response returns None → _EMPTY_RESULT; test explicitly |
| `impacted_companies` items missing `ticker` | Medium | Story requires the key; instruct LLM to use "N/A" if no ticker; missing key → item skipped |
| `confidence_score` returned as integer 1 | Low | float(1) → 1.0; clamping handles transparently |
| `reasoning_chain` items are non-strings (e.g. nested objects) | Medium | Validate isinstance(item, str) per item; invalid → return None from parser |
| LLM returns valid JSON but as a list not a dict | Medium | isinstance(data, dict) guard → return None |
| `confidence_score` key absent from response | Low | data.get returns None; float(None) raises TypeError → caught → None returned |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns dict with exactly 6 keys | Needs work | Module does not exist |
| `directly_affected_sectors` non-empty list of strings | Needs work | Validated in _parse_llm_response |
| `impacted_companies` items have name/ticker/impact_type | Needs work | Skip-invalid per item |
| `severity_level` one of LOW/MEDIUM/HIGH/CRITICAL | Needs work | Frozenset check + default to MEDIUM |
| `reasoning_chain` non-empty list of strings | Needs work | Validated in _parse_llm_response |
| `confidence_score` float in [0.0, 1.0] | Needs work | max(0.0, min(1.0, float(raw))) |
| None input → EMPTY_RESULT, no raise | Needs work | Pre-flight guard before LLM call |
| Empty string "" → EMPTY_RESULT, no raise | Needs work | not event_description or not event_description.strip() |
| Whitespace-only "   " → EMPTY_RESULT, no raise | Needs work | .strip() check in pre-flight |
| LLM confidence 1.5 → clamped to 1.0 | Needs work | min(1.0, ...) |
| LLM confidence -0.2 → clamped to 0.0 | Needs work | max(0.0, ...) |
| LLM severity_level "high" → normalised to "HIGH" | Needs work | .upper() before frozenset check |
| Malformed JSON → EMPTY_RESULT, no raise | Needs work | json.JSONDecodeError caught in _parse_llm_response |

---

## Suggested Test Classes for `tests/test_scenario.py`

| Class | Tests | Mocking |
|-------|-------|---------|
| `TestOutputSchema` | result is dict, has exactly 6 keys, types correct, key names exact, invalid input returns dict | @patch("data.scenario.anthropic.Anthropic") |
| `TestHappyPath` | all 6 fields populated, directly_affected_sectors non-empty, impacted_companies sub-keys present, reasoning_chain non-empty | same |
| `TestSeverityNormalisation` | lowercase "high" → "HIGH", mixed-case "Critical" → "CRITICAL", unknown "Severe" → "MEDIUM", all 4 valid values accepted | same |
| `TestConfidenceClamping` | 1.5 → 1.0, -0.2 → 0.0, 0.0 exact, 1.0 exact, integer 1 → float 1.0 | same |
| `TestFenceStripping` | JSON in ```json fence parsed correctly, plain JSON also parsed | same |
| `TestPreflightGuard` | None → EMPTY_RESULT, "" → EMPTY_RESULT, "   " → EMPTY_RESULT, all return confidence 0.0, none raise, no API call made | same |
| `TestLlmFailure` | malformed JSON → EMPTY_RESULT, Anthropic() raises → EMPTY_RESULT, JSON is list not dict → EMPTY_RESULT, empty directly_affected_sectors → EMPTY_RESULT | same |

---

## Dependencies

- `data/scenario.py` imports only `json` and `anthropic` — self-contained
- `tests/test_scenario.py` imports `simulate_scenario` from `data.scenario` only
- `@patch("data.scenario.anthropic.Anthropic")` is the only mock needed
- No changes to any existing module
- `anthropic` already in `requirements.txt`
