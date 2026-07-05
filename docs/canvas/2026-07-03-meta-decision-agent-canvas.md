# REASONS Canvas: Meta Decision Agent
Date: 2026-07-03
Analysis: 2026-07-03-meta-decision-agent-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The pipeline has four specialist signal agents (technical, fundamentals, sentiment, macro) each producing an independent action and confidence score, plus a risk module producing a risk level. There is no module that aggregates these into a single authoritative trade decision — downstream consumers must perform the aggregation themselves, which is error-prone and inconsistent.

**Goal:** A new `data/meta_agent.py` module with one public function `aggregate_signals(agent_outputs)` that performs confidence-weighted voting across all four signal agents, applies a risk penalty to the final confidence score, detects conflicts between agents, and returns a single final action with full auditability.

**Definition of Done:**
- [ ] Given all four signal agents return BUY, when `aggregate_signals` is called, then `final_action` is "BUY", `conflicts` is an empty list, and `confidence` is the mean of the four confidence values
- [ ] Given three agents return BUY and one returns SELL, when `aggregate_signals` is called, then `final_action` is "BUY", `conflicts` contains exactly one entry naming the dissenting agent and its vote, and `reasoning` mentions all four agents
- [ ] Given the risk level is HIGH and the pre-penalty confidence would be 0.875, when `aggregate_signals` is called, then the returned confidence is 0.875 × 0.80 = 0.70
- [ ] Given the risk level is CRITICAL, when `aggregate_signals` is called, then the returned confidence equals the pre-penalty confidence × 0.60, clamped to 0.0–1.0
- [ ] Given the risk level is LOW or MEDIUM, when `aggregate_signals` is called, then no penalty is applied and confidence equals the raw mean confidence of the winning agents
- [ ] Given two agents vote BUY (0.85, 0.90) and two vote SELL (0.80, 0.85) — an exact weighted tie — when `aggregate_signals` is called, then `final_action` is "HOLD" and both vote groups appear in `conflicts`
- [ ] Given the standard five-agent example with technical BUY/0.85, fundamentals BUY/0.90, sentiment SELL/0.65, macro HOLD/0.70, risk HIGH, when `aggregate_signals` is called, then `final_action` is "BUY", `confidence` is (0.85+0.90)/2 × 0.80 = 0.70, and `conflicts` has two entries
- [ ] Given `agent_outputs` is None, an empty dict, or missing any of the four signal-agent keys, when `aggregate_signals` is called, then it returns the `_EMPTY_RESULT` fallback with `final_action` "HOLD" and `confidence` 0.0, and does not raise
- [ ] Given any signal agent dict has a confidence value outside 0.0–1.0 or a non-string action, when `aggregate_signals` is called, then that agent is silently skipped and the remaining valid agents are used; if none remain, `_EMPTY_RESULT` is returned
- [ ] Given valid input, when `aggregate_signals` is called, then `confidence` is always a Python-native float in 0.0–1.0, `final_action` is always one of "BUY", "SELL", or "HOLD", `reasoning` is a non-empty str, and `conflicts` is a list

---

## E — Entities

### Module Components

| Component | Type | Responsibility |
|-----------|------|----------------|
| `_EMPTY_RESULT` | Module-level dict constant | Fallback returned via `.copy()` on any failure; `final_action: "HOLD"`, `confidence: 0.0`, `reasoning: ""`, `conflicts: []` |
| `_SIGNAL_AGENT_KEYS` | Module-level tuple constant | The four voting agent key names: technical, fundamentals, sentiment, macro; single source of truth |
| `_VALID_ACTIONS` | Module-level frozenset constant | The three legal action strings: "BUY", "SELL", "HOLD"; used to reject unknown action strings |
| `_RISK_PENALTIES` | Module-level dict constant | Maps risk level to confidence multiplier: LOW/MEDIUM → 1.0, HIGH → 0.80, CRITICAL → 0.60; unknown level falls back to 1.0 |
| `_parse_agent_entry(name, entry)` | Private helper | Validates one agent dict; returns (name, action, confidence) tuple if valid, None to skip; enforces dict type, action in _VALID_ACTIONS, confidence in [0.0, 1.0] |
| `_weighted_vote(parsed_entries)` | Private helper | Sums confidence per action across all valid agents; returns (winning_action, totals_dict); on exact tie between BUY and SELL returns "HOLD" as the winning action |
| `_compute_confidence(parsed_entries, winning_action, penalty)` | Private helper | Computes mean confidence of only the winning-action agents, multiplied by the risk penalty; clamps result to [0.0, 1.0]; returns Python-native float |
| `_detect_conflicts(parsed_entries, final_action)` | Private helper | Returns a list of descriptive strings, one for each valid agent whose action differs from final_action; includes HOLD dissenters |
| `_build_reasoning(parsed_entries, final_action, pre_penalty_conf, risk_level, penalty)` | Private helper | Returns a human-readable string naming each agent's vote and confidence, the raw pre-penalty confidence, and the risk penalty applied |
| `aggregate_signals(agent_outputs)` | Public function | Thin orchestrator; validates inputs, calls helpers in order, wraps everything in outer try/except; never raises |

### Input / Output Shape

| Field | Direction | Type | Notes |
|-------|-----------|------|-------|
| `technical` | Input | dict | Keys: `action` (str), `confidence` (float) |
| `fundamentals` | Input | dict | Keys: `action` (str), `confidence` (float) |
| `sentiment` | Input | dict | Keys: `action` (str), `confidence` (float) |
| `macro` | Input | dict | Keys: `action` (str), `confidence` (float) |
| `risk` | Input | dict | Key: `level` (str) |
| `final_action` | Output | str | One of "BUY", "SELL", "HOLD" |
| `confidence` | Output | float | Python-native float in [0.0, 1.0] |
| `reasoning` | Output | str | Non-empty on valid input; empty string on fallback |
| `conflicts` | Output | list[str] | Empty list when all agents agree; one entry per dissenter otherwise |

---

## A — Approach

**Pattern:** Pure-computation rule engine — same architectural family as `data/screener.py` and `data/graph_reasoning.py`

**Strategy:** A thin public orchestrator (`aggregate_signals`) delegates each algorithmic concern to a focused private helper. The four helpers are sequentially dependent: parsing produces the entries that voting consumes; voting's winning action drives conflict detection and confidence computation. All module-level constants serve as single sources of truth so that adding a new risk level or agent requires a single-line change. The outer `try/except Exception` on `aggregate_signals` is the universal safety net — private helpers may raise freely.

**Scope In:**
- Confidence-weighted voting over the four signal agent keys
- Risk penalty applied to final confidence (HIGH × 0.80, CRITICAL × 0.60)
- Conflict detection: any agent whose action differs from the final action
- Human-readable reasoning string
- Silent skip of invalid agent entries
- Tie-breaking: BUY-weight == SELL-weight → "HOLD"
- `_EMPTY_RESULT` fallback on None input, empty input, or all-invalid agents

**Scope Out:**
- No persistent storage of decisions or decision history
- No time-series aggregation across tickers or dates
- No dynamic weighting by agent track record
- No integration with `data/notifier.py` — sending the alert is a future story
- No streaming or async execution — inputs are already resolved dicts
- No risk override rules (e.g., "CRITICAL always forces HOLD") — penalty-only approach in this story

---

## S — Structure

**Module:** `Z:\claude\stock_analyzer\data\`

**New Files:**
- `data/meta_agent.py` — module-level constants, five private helpers, one public function `aggregate_signals`
- `tests/test_meta_agent.py` — pure-computation test suite, no mocking required

**Modified Files:**
- None — self-contained new module; no existing module imports it yet

**Database / External Dependencies:**
- None — pure Python stdlib, no HTTP, no LLM, no file I/O

---

## O — Operations

1. Create `data/meta_agent.py` — module-level constants block: `_EMPTY_RESULT`, `_SIGNAL_AGENT_KEYS`, `_VALID_ACTIONS`, `_RISK_PENALTIES`

2. Add `_parse_agent_entry(name, entry)` to `data/meta_agent.py` — validates one agent dict; returns (name, action, confidence) tuple or None; checks isinstance dict, action in `_VALID_ACTIONS`, confidence is float or int and in [0.0, 1.0]

3. Add `_weighted_vote(parsed_entries)` to `data/meta_agent.py` — sums confidence per action; handles exact BUY/SELL tie by returning "HOLD"; returns (winning_action, totals_dict)

4. Add `_compute_confidence(parsed_entries, winning_action, penalty)` to `data/meta_agent.py` — filters entries to winning action; computes their mean confidence; multiplies by penalty; clamps to [0.0, 1.0]; returns Python float

5. Add `_detect_conflicts(parsed_entries, final_action)` to `data/meta_agent.py` — builds and returns a list of descriptive strings for each agent whose action differs from final_action; includes HOLD dissenters

6. Add `_build_reasoning(parsed_entries, final_action, pre_penalty_conf, risk_level, penalty)` to `data/meta_agent.py` — returns a single human-readable string: lists each agent name, its action, its confidence; appends the risk level, penalty multiplier, and final pre/post penalty figures

7. Add `aggregate_signals(agent_outputs)` to `data/meta_agent.py` — thin orchestrator: guards None/non-dict input; calls `_parse_agent_entry` for each key in `_SIGNAL_AGENT_KEYS`; returns `_EMPTY_RESULT.copy()` if no valid entries; calls vote → confidence → conflicts → reasoning; extracts risk level from `agent_outputs.get("risk", {}).get("level")`; applies penalty via `_RISK_PENALTIES.get(level, 1.0)`; wraps all in outer `try/except Exception`

8. Create `tests/test_meta_agent.py` — seven test classes covering schema contract, unanimous BUY/SELL/HOLD paths, risk penalty variants, tie-breaking, conflict detection, preflight failures (None/empty/missing keys), and invalid-entry skip behaviour; no mocking required

---

## N — Norms

- Pure Python 3.9.12 — no third-party imports; stdlib only
- Module-per-concern: one public function per module
- Module-level constants for all lookup tables and fallback dicts; always `.copy()` on return
- Private helpers prefixed with `_`; named after what they compute, not how
- `_EMPTY_RESULT` must be a module-level constant dict with all four output keys present
- Every public function wraps its body in `try/except Exception` and returns the fallback dict — never raises
- Return types must be Python-native: `float` not `numpy.float64`, `list` not generator, `str` not bytes
- Confidence values clamped to [0.0, 1.0] — never return a negative or greater-than-one confidence
- Test files import only from the module under test plus `unittest`; no mocking required for pure-computation modules

---

## S — Safeguards

- `_EMPTY_RESULT` must include all four output keys (`final_action`, `confidence`, `reasoning`, `conflicts`) — partial fallback dicts cause KeyError in downstream consumers
- Guard the empty-entries case before calling `_compute_confidence` — dividing by zero if all entries are skipped would bypass the outer try/except and return garbage
- `_RISK_PENALTIES.get(level, 1.0)` — unknown risk level must not raise; fallback 1.0 is the correct no-penalty sentinel
- `_parse_agent_entry` must accept `confidence` as either float or int (int is valid Python; `0` and `1` are boundary values) and convert to float for computation
- Tie detection compares summed float weights — use symmetric test inputs (same confidence both sides) in tests to guarantee exact equality without rounding surprises
- The `reasoning` string must be non-empty on any valid aggregation — even a single-agent result needs a meaningful string; test this explicitly
- No import of `data.screener`, `data.risk`, or any other pipeline module — `meta_agent` is self-contained and must not create circular import chains
- Outer `try/except` on `aggregate_signals` must not swallow the wrong level — private helpers may raise; the public function catches everything and returns `_EMPTY_RESULT.copy()`
