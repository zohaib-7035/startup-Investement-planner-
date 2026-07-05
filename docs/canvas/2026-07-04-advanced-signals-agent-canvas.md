# REASONS Canvas: Advanced Signals Agent
Date: 2026-07-04
Analysis: 2026-07-04-advanced-signals-agent-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The platform has a `generate_recommendation` function in `screener.py` that evaluates RSI and EPS but has no module for multi-indicator trend-strength signals. There is no way to evaluate ADX trend strength, ATR volatility, price momentum, and volume confirmation together in a single, self-contained rule engine.

**Goal:** Create `data/signals.py` with a single public function `generate_advanced_signal` that evaluates four technical indicators and returns a BUY, SELL, HOLD, or WATCHLIST recommendation with a confidence score and human-readable reason — with no LLM call, no external HTTP, and no dependency on any other `data/` module.

**Definition of Done:**
- [ ] Given `adx=38, atr=4.2, momentum=0.15, volume_ratio=1.8`, when called, then returns action "BUY" with confidence 0.85 and a non-empty reason string
- [ ] Given `adx=32, atr=3.1, momentum=-0.12, volume_ratio=1.6`, when called, then returns action "SELL" with confidence 0.75
- [ ] Given `adx=22, atr=2.0, momentum=0.05, volume_ratio=1.1`, when called, then returns action "WATCHLIST" with confidence 0.55
- [ ] Given `adx=15, atr=1.5, momentum=0.02, volume_ratio=0.9`, when called, then returns action "HOLD" with confidence 0.40
- [ ] Given `adx=38, atr=6.5, momentum=0.15, volume_ratio=1.8` (ATR above 5.0), when called, then returns action "BUY" with confidence 0.765 (10% reduction applied)
- [ ] Given None as any input parameter, when called, then returns action "HOLD", confidence 0.0, and a reason indicating invalid input — and does not raise
- [ ] Given a non-numeric string or negative value for adx, atr, or volume_ratio, when called, then returns confidence 0.0 and does not raise
- [ ] Given `adx=26, momentum=0.05, volume_ratio=1.5` (BUY boundary), when called, then returns action "BUY" (strict greater-than for ADX, greater-than-or-equal for volume_ratio)
- [ ] Given `adx=25, momentum=0.05, volume_ratio=1.5` (ADX exactly 25), when called, then returns action "WATCHLIST" (ADX is not greater than 25, so BUY rule does not fire)
- [ ] All 448 existing tests still pass after adding the new module
- [ ] Test review passes with recommendation: Ready (no Meaningless tests)

---

## E — Entities

### Module Entities

| Entity | Type | Key Attributes | Notes |
|--------|------|----------------|-------|
| `data/signals.py` | New Python module | One public function, four private helpers/constants | Does not exist; to be created |
| `generate_advanced_signal` | Public function | Takes adx, atr, momentum, volume_ratio; returns dict with action, confidence, reason | Never raises; outer try/except wraps entire body |
| `_CONFIDENCE_MAP` | Module-level dict constant | Four keys: BUY→0.85, SELL→0.75, WATCHLIST→0.55, HOLD→0.40 | Same pattern as screener.py's _CONFIDENCE_MAP |
| `_INVALID_INPUT_FALLBACK` | Module-level dict constant | action "HOLD", confidence 0.0, reason string describing invalid input | Returned when any parameter fails validation; confidence 0.0 distinguishes invalid HOLD from real HOLD at 0.40 |
| `_ATR_HIGH_THRESHOLD` | Module-level float constant | Value: 5.0 | ATR values above this trigger the volatility penalty |
| `_ATR_VOLATILITY_PENALTY` | Module-level float constant | Value: 0.90 | Multiplier applied to confidence when ATR exceeds threshold |
| `_safe_indicator` | Private helper function | Accepts value, optional min_val, optional max_val; returns float or None | Generalisation of screener.py's _safe_rsi; validates any numeric indicator; returns None on invalid input to trigger pre-flight guard |
| `_apply_atr_modifier` | Private helper function | Accepts confidence float and atr float; returns float | Applies volatility penalty when ATR exceeds threshold; isolated so it is independently testable |
| `tests/test_signals.py` | New test file | Seven test classes; no mocking | Imports generate_advanced_signal from data.signals only |

**Existing entities referenced but not modified:**

| Entity | Location | Relationship |
|--------|----------|-------------|
| `generate_recommendation` | `data/screener.py` | Shares the same {action, confidence, reason} return schema; signals.py is a parallel module, not a replacement |
| `_VALID_ACTIONS` | `data/meta_agent.py:10` | frozenset of BUY, SELL, HOLD — WATCHLIST is intentionally absent; callers must handle WATCHLIST before passing to aggregate_signals |
| `parallel_runner.py` | `data/parallel_runner.py` | Not modified in this story; future integration story required to wire generate_advanced_signal in |

---

## A — Approach

**Pattern:** Pure rule-based Python function following the screener.py module-per-concern pattern — module-level constants, private validation helper, private modifier helper, public function with pre-flight guard and ordered if/elif/else rule block.

**Strategy:** `generate_advanced_signal` mirrors `generate_recommendation` structurally: constants define thresholds and fallbacks, `_safe_indicator` normalises all four inputs before any rule evaluation (returning None on failure), the public function early-returns `_INVALID_INPUT_FALLBACK` if any input is invalid, and an ordered if/elif/else block implements the four rules. The ATR confidence modifier is deliberately isolated in `_apply_atr_modifier` rather than inlined into each rule branch — this keeps the rule engine (what action fires) and the post-rule adjustment (how confident we are) independently testable. An outer `try/except Exception` wraps the entire function body.

**Scope In:**
- `data/signals.py` with one public function and five supporting constants/helpers
- `tests/test_signals.py` with seven test classes covering all acceptance criteria
- WATCHLIST as a new action string (signals.py-scoped; not added to meta_agent._VALID_ACTIONS)
- ATR used only as a confidence modifier, not for position sizing

**Scope Out:**
- No integration with `parallel_runner.py` — that is a future story
- No changes to `meta_agent.py`, `screener.py`, or any existing module
- No RSI, EPS, or fundamental inputs
- No multi-timeframe analysis
- No position sizing or stop-loss calculations from ATR
- No combination or blending of signals.py output with generate_recommendation output

---

## S — Structure

**Module directory:** `Z:\claude\stock_analyzer\data\`

**New Files:**
- `data/signals.py` — complete signals module with constants, helpers, and generate_advanced_signal
- `tests/test_signals.py` — test suite for generate_advanced_signal

**Modified Files:**
- None — no existing module is changed

**Database / External:**
- None — pure computation, stdlib only (import math)

---

## O — Operations

1. Define module-level fallback and confidence constants in `data/signals.py`: `_INVALID_INPUT_FALLBACK` as a dict with action "HOLD", confidence 0.0, and a descriptive reason string; `_CONFIDENCE_MAP` as a dict mapping all four action strings to their base confidence floats

2. Define module-level ATR threshold constants in `data/signals.py`: `_ATR_HIGH_THRESHOLD` as 5.0 and `_ATR_VOLATILITY_PENALTY` as 0.90

3. Implement `_safe_indicator(value, min_val, max_val)` private helper in `data/signals.py`: accepts any value and optional inclusive lower/upper bounds; uses math.isfinite to reject NaN and infinity; rejects non-numeric values via a try/except around float() cast; rejects values outside the specified bounds; returns the validated float or None on any failure

4. Implement `_apply_atr_modifier(confidence, atr)` private helper in `data/signals.py`: accepts a validated confidence float and a validated ATR float; returns confidence multiplied by _ATR_VOLATILITY_PENALTY when atr is strictly greater than _ATR_HIGH_THRESHOLD; returns confidence unchanged otherwise

5. Implement `generate_advanced_signal(adx, atr, momentum, volume_ratio)` public function in `data/signals.py`: wrap the entire body in an outer try/except Exception that returns _INVALID_INPUT_FALLBACK on any unexpected error; validate all four inputs using _safe_indicator with appropriate bounds (adx: 0 to 100 inclusive, atr: 0 to no upper bound, momentum: any finite float with no bounds, volume_ratio: 0 to no upper bound); return _INVALID_INPUT_FALLBACK immediately if any validated value is None; implement the ordered rule set — Rule 1 BUY fires when adx is strictly greater than 25 AND momentum is strictly greater than 0 AND volume_ratio is at least 1.5, Rule 2 SELL fires when adx is strictly greater than 25 AND momentum is strictly less than 0 AND volume_ratio is at least 1.5, Rule 3 WATCHLIST fires when adx is between 20 and 25 inclusive, Rule 4 HOLD fires for all other cases; look up base confidence from _CONFIDENCE_MAP for the matched action; apply _apply_atr_modifier to the base confidence using the validated ATR value; return the result dict with action string, final confidence float, and a human-readable reason string that names the triggered rule and the relevant indicator values; docstring must note that WATCHLIST is not in meta_agent._VALID_ACTIONS and callers must handle it before passing to aggregate_signals

6. Implement `tests/test_signals.py` with seven test classes — TestOutputSchema covers result is dict, has exactly three keys, action is string, confidence is float, reason is non-empty string; TestBuyRule covers the happy path from AC1, boundary adx=26, volume_ratio exactly 1.5, and high-ATR penalty from AC5 using pytest.approx; TestSellRule covers the happy path from AC2, negative momentum, and high-ATR penalty applied to SELL confidence using pytest.approx; TestWatchlistRule covers the happy path from AC3, adx=25 boundary from AC9, adx=20 lower boundary, and ATR modifier applying to WATCHLIST confidence; TestHoldRule covers the happy path from AC4, adx below 20, and momentum=0.0 with adx above 25 does not trigger BUY or SELL and falls to WATCHLIST or HOLD; TestAtrModifier covers ATR exactly 5.0 produces no penalty, ATR above 5.0 produces penalty with pytest.approx, and ATR None input triggers preflight fallback; TestPreflightGuard covers each of the four parameters individually set to None returns confidence 0.0 without raising, negative adx returns confidence 0.0, adx above 100 returns confidence 0.0, non-numeric string returns confidence 0.0, and NaN plus infinity return confidence 0.0

---

## N — Norms

### Python Pipeline Norms

- Module-per-concern pattern: one public function per module in `data/`
- Public function return type: dict with string keys — this module returns the three-key schema with action, confidence, and reason
- Exception boundary: outer try/except Exception wraps the entire function body — never re-raises, always returns the fallback dict on unexpected error
- Module-level constants: define fallback and confidence-map constants at module level so they are readable as documentation and patchable in tests
- Private helpers: prefix with underscore; each helper does one thing and is independently testable
- Action strings: uppercase throughout — "BUY", "SELL", "HOLD", "WATCHLIST" — matching the meta_agent.py and parallel_runner.py convention; do not use title-case like screener.py
- No imports from other `data/` modules — signals.py must be self-contained
- Python stdlib only — no third-party packages; import math is the only import
- Python 3.9.12 compatible — no walrus operator, no structural pattern matching

### Test Norms

- Plain unittest.TestCase — no mocking required (pure functions with no I/O)
- Test naming: test underscore what underscore condition underscore expected — describes the scenario, not just the method
- One assert per logical claim — prefer multiple focused assertions over one compound assertion
- Use pytest.approx for any floating-point comparison where the result passes through the ATR modifier (0.85 times 0.90 equals 0.7650000000000001 in Python float arithmetic)
- Module-level fixture dict for happy-path inputs — reuse across test classes with dict unpacking and key override pattern
- All tests Strong — no Meaningless tests (no assertions), no Weak tests (single trivial assertion)

---

## S — Safeguards

### Pipeline Safeguards

- Never raise to the caller — the outer try/except Exception is non-negotiable; any unhandled path must fall through to _INVALID_INPUT_FALLBACK
- Never import from other `data/` modules — signals.py must remain self-contained; circular import risk is high in a flat data package
- Confidence values must not exceed 1.0 or go below 0.0 — the ATR modifier multiplies by 0.90 which is safe for the current values, but future modifiers must clamp the result
- _INVALID_INPUT_FALLBACK must be returned by value — return a copy if mutable, not the constant itself, to protect against callers mutating it

### Feature-Specific Safeguards

- WATCHLIST and aggregate_signals: document in the generate_advanced_signal docstring that WATCHLIST is not in meta_agent._VALID_ACTIONS and will be silently dropped if passed to aggregate_signals without preprocessing — this is caller responsibility
- adx=25.0 boundary: the WATCHLIST rule uses inclusive bounds (20 to 25); the BUY/SELL rule uses strictly greater than 25 — these must not be reversed; test both adx=25 (WATCHLIST) and adx=26 (BUY) explicitly
- momentum=0.0: neither positive nor negative — must fall through past BUY and SELL rules; test this boundary explicitly in TestHoldRule
- ATR modifier applies to all four actions: the penalty reduces confidence universally to reflect elevated volatility risk — it applies to HOLD and WATCHLIST as well as BUY and SELL; test this for WATCHLIST explicitly
- Float precision: 0.85 times 0.90 equals 0.7650000000000001 in Python — all test assertions on modified confidence values must use pytest.approx

---

## Change Log

_No changes yet._
