# User Story: Scenario Simulation Agent
Date: 2026-07-04
Source: Pasted text

---

## Story 23: Simulate Market Impact of a Macroeconomic or Geopolitical Event

**As a** financial analyst using the AI Stock Intelligence Platform,
**I want** a scenario simulation engine that accepts a plain-language description of a macroeconomic or geopolitical event and returns a structured impact analysis,
**So that** I can understand which sectors and companies are directly and indirectly affected, how severe the impact is, and the causal chain driving those effects — without building a separate research workflow.

### Scope In
- New module `data/scenario.py` with one public function: `simulate_scenario(event_description)`
- Input: a single string describing the event (e.g. `"United States introduces new semiconductor export restrictions to China."`)
- Output dict with six keys: `directly_affected_sectors` (list of str), `indirectly_affected_sectors` (list of str), `impacted_companies` (list of dicts, each with `name`, `ticker`, `impact_type`), `severity_level` (str: one of `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`), `reasoning_chain` (list of str, ordered causal steps), `confidence_score` (float 0.0–1.0)
- LLM call to Claude Haiku via `anthropic.Anthropic()` — structured JSON prompt, same pattern as `knowledge_graph.py`
- `_EMPTY_RESULT` module-level fallback constant returned on invalid input or any exception
- `confidence_score` clamped to `[0.0, 1.0]` before returning
- `severity_level` normalised to uppercase; unknown values default to `"MEDIUM"`
- Markdown fence stripping before JSON parse (same as `rag_answer.py`)
- Never raises to the caller

### Scope Out
- No live news feed or web search — event description is caller-supplied text only
- No integration with `parallel_runner.py` in this story
- No historical backtesting of past events
- No portfolio rebalancing recommendations — impact analysis only
- No ticker price lookups or fundamentals fetch
- No multi-event correlation or portfolio-level aggregation

### Acceptance Criteria
- Given a valid event string `"United States introduces new semiconductor export restrictions to China."`, when `simulate_scenario(event_description)` is called, then it returns a dict with exactly the six keys `directly_affected_sectors`, `indirectly_affected_sectors`, `impacted_companies`, `severity_level`, `reasoning_chain`, `confidence_score`
- Given a valid event string, when called, then `directly_affected_sectors` is a non-empty list of strings and `indirectly_affected_sectors` is a list of strings (may be empty)
- Given a valid event string, when called, then each entry in `impacted_companies` is a dict with at least the keys `name`, `ticker`, `impact_type`
- Given a valid event string, when called, then `severity_level` is one of `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"` (uppercase normalised)
- Given a valid event string, when called, then `reasoning_chain` is a non-empty list of strings forming an ordered causal explanation
- Given a valid event string, when called, then `confidence_score` is a float clamped to `[0.0, 1.0]`
- Given `None` as `event_description`, when called, then it returns `_EMPTY_RESULT` with `confidence_score: 0.0` and does not raise
- Given an empty string `""` as `event_description`, when called, then it returns `_EMPTY_RESULT` with `confidence_score: 0.0` and does not raise
- Given a whitespace-only string `"   "` as `event_description`, when called, then it returns `_EMPTY_RESULT` with `confidence_score: 0.0` and does not raise
- Given the LLM returns a `confidence_score` of `1.5` (above 1.0), when called, then the returned `confidence_score` is clamped to `1.0`
- Given the LLM returns a `confidence_score` of `-0.2` (below 0.0), when called, then the returned `confidence_score` is clamped to `0.0`
- Given the LLM returns a `severity_level` of `"high"` (lowercase), when called, then the returned `severity_level` is normalised to `"HIGH"`
- Given the LLM returns an unparseable response (malformed JSON), when called, then it returns `_EMPTY_RESULT` and does not raise

### Definition of Done
- [ ] `data/scenario.py` implemented following module-per-concern pattern
- [ ] Exception boundary: outer `try/except` — never raises to caller
- [ ] `_EMPTY_RESULT` as module-level constant with all six keys set to safe defaults
- [ ] `confidence_score` clamped to `[0.0, 1.0]`
- [ ] `severity_level` normalised to uppercase with unknown-value fallback
- [ ] `tests/test_scenario.py` written with all tests Strong (no Meaningless, no Weak)
- [ ] All 498 existing tests still pass after adding the new module
- [ ] Test review passes: Recommendation: Ready

---
