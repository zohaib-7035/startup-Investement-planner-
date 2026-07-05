# Analysis: Meta Decision Agent

Date: 2026-07-03
Story: docs/story/2026-07-03-meta-decision-agent-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline, 15 modules under `data/`. This story is the pipeline's third pure-computation module (alongside `screener.py` and `graph_reasoning.py`) — no LLM, no HTTP, no external packages. `screener.py` is the closest structural model: module-level constant maps, private validation helpers, inline result-dict construction, never raises. `graph_reasoning.py` is the closest algorithmic model: skip-invalid per item, outer `try/except`, `_EMPTY_RESULT` as fallback. `risk.py` provides the `_RISK_THRESHOLDS` ordered-list pattern that maps cleanly to the risk penalty lookup.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_CONFIDENCE_MAP` module-level constant | `data/screener.py:3` | Maps action name to fixed confidence — same pattern as `_RISK_PENALTIES` dict needed here |
| `_INVALID_RSI_FALLBACK.copy()` fallback return | `data/screener.py:5` | Direct model for `_EMPTY_RESULT.copy()` — module-level dict constant returned on failure |
| `_safe_rsi(value)` private validation helper | `data/screener.py:12` | Skip-invalid pattern for a single field; meta_agent needs a per-agent-entry validator |
| Skip-invalid-per-item loop | `data/graph_reasoning.py:22` | Iterates items, silently skips malformed entries, continues with valid ones — exact pattern for skipping invalid agent dicts |
| `_EMPTY_RESULT` as static dict constant | `data/risk.py:5` | Returned via `.copy()` on any failure — structural model for `_EMPTY_RESULT` in meta_agent |
| `_RISK_THRESHOLDS` ordered list | `data/risk.py:15` | Ordered lookup for threshold → label — maps to `_RISK_PENALTIES` dict here |
| Outer `try/except Exception → fallback.copy()` | `data/graph_reasoning.py:98` | Universal safety net; `aggregate_signals` must follow the same contract |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/meta_agent.py` | New Python module | Does not exist; owns all signal aggregation logic |
| `aggregate_signals(agent_outputs)` | Public function | Thin orchestrator: validate → vote → detect conflicts → build reasoning → apply penalty → return |
| `_EMPTY_RESULT` | Module-level dict constant | `{final_action: "HOLD", confidence: 0.0, reasoning: "", conflicts: []}` — returned via `.copy()` on any failure |
| `_SIGNAL_AGENT_KEYS` | Module-level constant | Tuple of the four agent key names: `("technical", "fundamentals", "sentiment", "macro")` |
| `_VALID_ACTIONS` | Module-level constant | `frozenset({"BUY", "SELL", "HOLD"})` — used to reject unknown action strings |
| `_RISK_PENALTIES` | Module-level dict constant | `{"LOW": 1.0, "MEDIUM": 1.0, "HIGH": 0.80, "CRITICAL": 0.60}` — fallback 1.0 for unknown levels |
| `_parse_agent_entry(name, entry)` | Private helper | Returns `(name, action, confidence)` tuple if valid, `None` to skip; checks dict type, action in `_VALID_ACTIONS`, confidence in `[0.0, 1.0]` |
| `_weighted_vote(parsed_entries)` | Private helper | Sums confidence per action; returns `(winning_action, totals_dict)`; on tie → returns `"HOLD"` as winning action |
| `_compute_confidence(parsed_entries, winning_action, penalty)` | Private helper | Mean of winning agents' confidence × penalty, clamped to `[0.0, 1.0]`, returned as Python `float` |
| `_detect_conflicts(parsed_entries, final_action)` | Private helper | Returns `list[str]` — one descriptive string per agent whose action differs from `final_action` |
| `_build_reasoning(parsed_entries, final_action, pre_penalty_conf, risk_level, penalty)` | Private helper | Returns non-empty string naming each agent's vote and confidence, plus risk penalty applied |
| `tests/test_meta_agent.py` | New test file | Pure computation — no mocking required |

---

## Strategic Approach

`data/meta_agent.py` follows the rule-engine pattern of `screener.py` and `graph_reasoning.py`: a thin public orchestrator delegates to focused private helpers, each testable in isolation. The aggregation algorithm has four sequential concerns — validate inputs, compute weighted vote, detect conflicts, build human-readable reasoning — and each maps to exactly one private helper. The tie-breaking rule (`HOLD` wins on equal weighted votes) is the only non-obvious invariant and must be locked down by a dedicated test. All module-level constants (`_SIGNAL_AGENT_KEYS`, `_VALID_ACTIONS`, `_RISK_PENALTIES`) serve as the single source of truth so that adding a new risk level or agent in the future requires a single-line change.

---

## Key Design Decisions

- `_EMPTY_RESULT` has `final_action: "HOLD"` and `confidence: 0.0` — HOLD is the most conservative fallback; 0.0 signals "no data" rather than a real HOLD recommendation
- **Confidence = mean of winning-action agents × risk penalty** — not a global mean across all agents; only agents that agreed with the winner contribute to output confidence. This prevents a high-confidence SELL from inflating a BUY confidence.
- **Tie → `"HOLD"`** — when BUY-weight equals SELL-weight exactly, neither is dominant; HOLD is the correct conservative response; all tied action groups appear in `conflicts`
- `_parse_agent_entry` silently skips invalid entries — matches the `graph_reasoning.py` skip-invalid-per-item pattern; partial data is better than total failure
- `_RISK_PENALTIES` fallback is 1.0 — unknown risk levels (`None`, unrecognised strings) apply no penalty and do not cause an exception
- **`conflicts` includes HOLD dissenters** — any agent whose action differs from the winner is a conflict, including HOLD agents in a BUY decision. The story's standard example has 2 conflicts: sentiment (SELL) and macro (HOLD).
- **`reasoning` is a `str`, not `list`** — downstream gets one human-readable string; `conflicts` is already the structured list for programmatic use
- **Pure stdlib only** — no `numpy`, no `math` needed; all arithmetic is Python float operations

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Floating-point equality in tie detection | Medium | Constructed tie scenarios in tests should use two agents each side with the same confidence values to guarantee exact equality |
| All agents invalid after skip-invalid pass | Medium | `parsed_entries` empty → must return `_EMPTY_RESULT.copy()` before calling `_compute_confidence` (division by zero guard) |
| Missing `risk` key in `agent_outputs` | Low | `_RISK_PENALTIES.get(level, 1.0)` with `level = None` → returns 1.0 safely; or guard missing risk key returning no-penalty |
| Agent with `confidence=0.0` (boundary value) | Low | Valid entry; contributes 0.0 weight to the vote (no effect), which is correct |
| `reasoning` empty string on fallback | Low | `_EMPTY_RESULT` has `reasoning: ""` — story only requires non-empty on valid input |
| Only 1 of 4 agent keys present | Low | Aggregation proceeds with surviving agent; single-agent result is valid (final_action = that agent's action, no conflicts) |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| All BUY → final_action=BUY, conflicts=[] | Needs work | Pure computation test |
| 3 BUY + 1 SELL → final_action=BUY, 1 conflict | Needs work | Conflict detection; dissenting agent named in string |
| HIGH risk penalty 0.875 × 0.80 = 0.70 | Needs work | Verified by formula; `_RISK_PENALTIES["HIGH"] = 0.80` |
| CRITICAL risk penalty × 0.60 | Needs work | Same mechanism |
| LOW/MEDIUM no penalty | Needs work | `_RISK_PENALTIES` values of 1.0 |
| Tie 2 BUY + 2 SELL → HOLD, both groups in conflicts | Needs work | `_weighted_vote` tie-breaker; both groups in `conflicts` |
| Standard 5-agent example → BUY, conf=0.70, 2 conflicts | Needs work | Integration test verifying full formula end-to-end |
| None/empty/missing-key → HOLD, 0.0, no raise | Needs work | Preflight guard before calling helpers |
| Invalid confidence or action → silently skip | Needs work | `_parse_agent_entry` skip-invalid |
| Type contract: float, str∈{BUY/SELL/HOLD}, str, list | Needs work | `assertIs(type(...), float)` pattern from test_risk.py |

---

## Dependencies

- No other `data/` module imported — `meta_agent.py` is self-contained; accepts pre-resolved dicts
- `data/screener.py` — producer of the `technical` signal's `{action, confidence}` dict (one hop, read-only)
- `data/risk.py` — producer of the `risk` signal's `{level}` dict (one hop, read-only)
- No new packages required — pure Python stdlib only
