# User Story: Meta Decision Agent

Date: 2026-07-03
Source: Pasted text

---

## Story 17: Aggregate Multi-Agent Signals into a Final Trade Decision

**As a** system orchestrating the stock intelligence pipeline,
**I want** a single `aggregate_signals(agent_outputs)` function that accepts the outputs of the technical, fundamentals, sentiment, and macro agents alongside the risk level, computes a confidence-weighted vote, detects conflicts between agents, and returns a final action with a risk-adjusted confidence score, reasoning trace, and conflict list,
**So that** downstream consumers receive one authoritative trade decision with full auditability of how it was derived and what disagreements exist across the specialist agents.

### Scope In
- New module `data/meta_agent.py` exposing one public function `aggregate_signals(agent_outputs)`
- `agent_outputs` accepts a dict with keys `technical`, `fundamentals`, `sentiment`, `macro` (each a dict with `action: str` and `confidence: float`) and `risk` (a dict with `level: str`)
- Confidence-weighted voting: each signal agent votes for its action weighted by its confidence; the action with the highest total weight wins
- Conflict detection: any agent whose action differs from the final action is flagged as a conflict in the `conflicts` list with a descriptive string
- Risk penalty applied to the final confidence: `HIGH` × 0.80, `CRITICAL` × 0.60; `LOW` and `MEDIUM` carry no penalty
- Final confidence is the mean confidence of the winning-action agents, post risk-penalty, clamped to `[0.0, 1.0]`
- `reasoning` is a human-readable string that names each agent, its vote, and its confidence, plus the risk penalty applied
- Returns `{final_action (str), confidence (float), reasoning (str), conflicts (list[str])}`
- Module-level `_EMPTY_RESULT` constant; outer `try/except` on `aggregate_signals`; never raises
- Pure Python — no LLM calls, no HTTP calls, no external packages beyond stdlib

### Scope Out
- No persistent storage of decisions or decision history
- No time-series aggregation across multiple tickers or dates
- No dynamic weighting by agent track record or rolling accuracy
- No integration with `data/notifier.py` (sending the final decision as an alert is a future story)
- No streaming or async execution of the specialist agents — inputs are already resolved dicts
- Risk override rules (e.g. "CRITICAL risk always forces HOLD") are out of scope — penalty-only approach in this story

### Acceptance Criteria

- **Given** all four signal agents return `BUY`, **when** `aggregate_signals` is called, **then** it returns `{final_action: "BUY", confidence: <mean of their four confidence values>, reasoning: <non-empty string>, conflicts: []}` and `conflicts` is an empty list.

- **Given** three agents return `BUY` and one returns `SELL`, **when** `aggregate_signals` is called, **then** `final_action` is `"BUY"`, `conflicts` contains exactly one entry naming the dissenting agent and its vote, and `reasoning` mentions all four agents.

- **Given** the risk level is `HIGH`, **when** `aggregate_signals` is called with a BUY-winning result whose pre-penalty confidence would be 0.875, **then** the returned `confidence` is `0.875 × 0.80 = 0.70` (rounded to Python float precision).

- **Given** the risk level is `CRITICAL`, **when** `aggregate_signals` is called, **then** the returned `confidence` equals the pre-penalty confidence × 0.60, clamped to `[0.0, 1.0]`.

- **Given** the risk level is `LOW` or `MEDIUM`, **when** `aggregate_signals` is called, **then** no penalty is applied and `confidence` equals the raw mean confidence of the winning agents.

- **Given** two agents return `BUY` (confidence 0.85, 0.90) and two return `SELL` (confidence 0.80, 0.85) — an exact weighted tie — **when** `aggregate_signals` is called, **then** `final_action` is `"HOLD"` (tie-breaker) and both vote groups appear in `conflicts`.

- **Given** the standard five-agent example `{technical: BUY/0.85, fundamentals: BUY/0.90, sentiment: SELL/0.65, macro: HOLD/0.70, risk: HIGH}`, **when** `aggregate_signals` is called, **then** `final_action` is `"BUY"`, `confidence` is `round((0.85+0.90)/2 * 0.80, 10)`, `conflicts` has two entries (sentiment SELL and macro HOLD), and `reasoning` is a non-empty string.

- **Given** `agent_outputs` is `None`, an empty dict, or missing any of the four signal-agent keys, **when** `aggregate_signals` is called, **then** it returns `_EMPTY_RESULT.copy()` with `final_action: "HOLD"`, `confidence: 0.0`, and does not raise.

- **Given** any signal agent dict has a `confidence` value outside `[0.0, 1.0]` or a non-string `action`, **when** `aggregate_signals` is called, **then** that agent's entry is silently skipped and the remaining valid agents are used; if no valid agents remain, `_EMPTY_RESULT.copy()` is returned.

- **Given** valid input, **when** `aggregate_signals` is called, **then** `confidence` is always a Python-native `float` in `[0.0, 1.0]`, `final_action` is always one of `"BUY"`, `"SELL"`, or `"HOLD"`, `reasoning` is a non-empty `str`, and `conflicts` is a `list`.

### Definition of Done
- [ ] `data/meta_agent.py` implemented with `aggregate_signals()` and `_EMPTY_RESULT`
- [ ] Pure Python — no LLM, no HTTP, no imports beyond stdlib
- [ ] `tests/test_meta_agent.py` written; all tests pass; no mocking required
- [ ] `/test-review` run — Recommendation: Ready
- [ ] No regression in existing 221 tests
- [ ] All 10 acceptance criteria above have a corresponding test
