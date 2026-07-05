# Analysis: Advanced Signals Agent
Date: 2026-07-04
Story: 2026-07-04-advanced-signals-agent-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with 21 modules under `data/`, each following module-per-concern pattern. The closest existing parallel is `data/screener.py` — a pure rule-based function with the same `{action, confidence, reason}` return schema, `_CONFIDENCE_MAP` constant, `_INVALID_*_FALLBACK` constant, `_safe_*` validation helper, and no external calls. No frontend repo. No new packages required — stdlib only (`math`).

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `{action, confidence, reason}` return schema | `data/screener.py` | Exact schema to reuse — `generate_recommendation` returns the same 3-key dict |
| `_CONFIDENCE_MAP` pattern | `data/screener.py` | Module-level dict mapping action string → float; signals.py extends to 4 keys |
| `_INVALID_RSI_FALLBACK` pattern | `data/screener.py` | Module-level constant for invalid-input return; signals.py uses `_INVALID_INPUT_FALLBACK` with `confidence: 0.0` |
| `_safe_rsi(value)` validation helper | `data/screener.py` | Uses `math.isfinite`, range check, `float()` cast; signals.py generalises this into `_safe_indicator` with optional min/max constraints |
| `try/except Exception` outer boundary | All 21 `data/` modules | Universal pattern — `generate_advanced_signal` must follow it |
| `_VALID_ACTIONS = frozenset({"BUY", "SELL", "HOLD"})` | `data/meta_agent.py:10` | **Critical:** meta_agent does NOT include WATCHLIST — `_parse_agent_entry` returns `None` for unknown actions, so WATCHLIST is silently dropped if passed to `aggregate_signals`. This is intentional gating, not a bug. |
| Uppercase action convention | `data/meta_agent.py`, `data/parallel_runner.py` | meta_agent and parallel_runner use uppercase `"BUY"/"SELL"/"HOLD"`. By contrast, `screener.py` uses title-case `"Buy"/"Sell"/"Hold"` and parallel_runner normalises it with `.upper()`. signals.py must output uppercase natively to avoid requiring normalisation. |
| `generate_recommendation` in parallel pipeline | `data/parallel_runner.py:6` | parallel_runner imports `generate_recommendation` from screener.py for `_run_technical_agent`. signals.py is **not wired into parallel_runner in this story** — that is a future integration story. |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `data/signals.py` | New Python module | Does not exist; to be created |
| `generate_advanced_signal(adx, atr, momentum, volume_ratio)` | Public function | Returns `{action, confidence, reason}` dict; never raises |
| `_INVALID_INPUT_FALLBACK` | Module-level dict constant | `{action: "HOLD", confidence: 0.0, reason: "..."}` — returned when any input fails validation |
| `_CONFIDENCE_MAP` | Module-level dict constant | 4-key map: `BUY→0.85, SELL→0.75, WATCHLIST→0.55, HOLD→0.40` |
| `_ATR_HIGH_THRESHOLD` | Module-level float constant | `5.0` — ATR above this value triggers a 10% confidence reduction |
| `_ATR_VOLATILITY_PENALTY` | Module-level float constant | `0.90` — multiplier applied when ATR > threshold |
| `_safe_indicator(value, min_val, max_val)` | Private helper | Generalisation of `_safe_rsi`: validates any numeric indicator with optional lower/upper bounds; returns `float` or `None`; handles None, non-numeric, NaN/infinity |
| `_apply_atr_modifier(confidence, atr)` | Private helper | Applies volatility penalty when ATR exceeds threshold; returns `float` — separation keeps the rule logic and modifier logic independently testable |
| `"WATCHLIST"` action | New action string | First appearance in the codebase — not in `meta_agent._VALID_ACTIONS`; callers downstream must handle WATCHLIST before passing to aggregate_signals |
| `tests/test_signals.py` | New test file | Pure Python, no mocking; target: all tests Strong |

---

## Strategic Approach

`generate_advanced_signal` follows the `screener.py` pattern exactly: module-level constants define the rule thresholds and fallbacks, a private `_safe_indicator` helper normalises each input (returning `None` on invalid values so the main function can early-return the fallback before any rule evaluation), and an ordered if/elif/else block implements the four rules. The only novel element is the ATR confidence modifier — isolated in `_apply_atr_modifier` so it is independently testable without triggering a full rule evaluation. An outer `try/except Exception` wraps the entire function body.

---

## Key Design Decisions

- **Uppercase action strings throughout** — signals.py outputs `"BUY"`, `"SELL"`, `"HOLD"`, `"WATCHLIST"` in uppercase to match the meta_agent/parallel_runner convention; `screener.py`'s title-case ("Buy") is a legacy inconsistency that required a `.upper()` normalisation step in `parallel_runner._run_technical_agent`. signals.py must not repeat that pattern.
- **WATCHLIST is signals.py-scoped; it is not a valid input to `aggregate_signals`** — `meta_agent._VALID_ACTIONS` is `frozenset({"BUY", "SELL", "HOLD"})`; WATCHLIST would be silently skipped. The docstring of `generate_advanced_signal` must note that callers must handle WATCHLIST before passing the result to aggregate_signals. No change to meta_agent.py in this story.
- **`_safe_indicator` accepts min/max constraints** — ADX needs `[0, 100]`, ATR and volume_ratio need `[0, ∞)`, and momentum accepts any finite float. One helper with optional bounds is cleaner than four separate validators.
- **ATR modifier isolated in `_apply_atr_modifier`** — keeps the rule engine (if/elif/else) and the post-rule adjustment (ATR penalty) separately testable; prevents the modifier logic from coupling into every rule branch.
- **`_INVALID_INPUT_FALLBACK` returns `action: "HOLD"` with `confidence: 0.0`** — matches the `_INVALID_RSI_FALLBACK` convention in screener.py; `confidence: 0.0` is the sentinel that distinguishes invalid-input HOLD from a real HOLD signal at `0.40`.
- **No imports from other `data/` modules** — signals.py is self-contained; future integration with parallel_runner is a separate story.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| WATCHLIST silently dropped by `aggregate_signals` if caller does not handle it | High | Document in docstring; caller responsibility — do not change meta_agent in this story |
| `momentum = 0.0` — neither positive nor negative — hits no BUY/SELL rule; falls through to WATCHLIST or HOLD depending on ADX | Medium | ADX > 25 AND momentum == 0 AND volume_ratio >= 1.5 → BUY rule requires `momentum > 0` (strict), so this falls to WATCHLIST (if ADX 20–25) or HOLD. Must be tested explicitly. |
| `volume_ratio = 1.5` exactly — boundary BUY/SELL rule uses `>=`; must confirm `>=` not `>` | Medium | Story AC 8 explicitly requires `>=` for volume_ratio; test the exact boundary value |
| `adx = 25.0` exactly — WATCHLIST rule uses `>= 20 AND <= 25` (inclusive); BUY/SELL rule uses `> 25` (strict); must confirm these are not reversed | High | Story AC 9 tests this boundary explicitly; test both `adx=25` → WATCHLIST and `adx=26` → BUY |
| ATR modifier applied to HOLD/WATCHLIST — story does not specify whether penalty applies to all actions or only BUY/SELL | Medium | Story says ATR modifier adjusts confidence "to reflect elevated volatility risk" — applies to all actions; makes WATCHLIST confidence 0.495 when ATR is high. Test this explicitly. |
| `atr = None` with valid ADX/momentum/volume_ratio — ATR validation fails → `_INVALID_INPUT_FALLBACK` returned | Medium | Story says "None as any input parameter" returns confidence 0.0; test this individually for each parameter |
| `confidence` float precision — `0.85 * 0.90 = 0.7650000000000001` in Python float arithmetic | Low | Wrap result in `round(x, 10)` or use `pytest.approx` in tests; story AC says `0.765` — use `pytest.approx` in test assertions |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| `adx=38, atr=4.2, momentum=0.15, volume_ratio=1.8` → BUY, confidence 0.85 | Needs work | Module does not exist; rule 1 fires; ATR 4.2 < 5.0 so no penalty |
| `adx=32, atr=3.1, momentum=-0.12, volume_ratio=1.6` → SELL, confidence 0.75 | Needs work | Rule 2 fires; ATR below threshold |
| `adx=22, atr=2.0, momentum=0.05, volume_ratio=1.1` → WATCHLIST, confidence 0.55 | Needs work | Rule 3 fires (ADX 20–25); volume_ratio 1.1 < 1.5 so rules 1 and 2 would not fire anyway |
| `adx=15, atr=1.5, momentum=0.02, volume_ratio=0.9` → HOLD, confidence 0.40 | Needs work | ADX < 20 so WATCHLIST rule does not fire either; falls to HOLD |
| `adx=38, atr=6.5, momentum=0.15, volume_ratio=1.8` → BUY, confidence 0.765 | Needs work | Rule 1 fires; ATR 6.5 > 5.0 triggers penalty: 0.85 × 0.90 = 0.765 |
| None as any input → action HOLD, confidence 0.0, no exception | Needs work | `_safe_indicator` returns None → pre-flight returns `_INVALID_INPUT_FALLBACK` |
| Non-numeric or negative adx/atr/volume_ratio → confidence 0.0, no exception | Needs work | Same pre-flight path |
| `adx=26, volume_ratio=1.5` → BUY (strict `>` for ADX, `>=` for volume_ratio) | Needs work | Boundary test for rule 1 |
| `adx=25, momentum=0.05, volume_ratio=1.5` → WATCHLIST (ADX not > 25) | Needs work | Boundary test confirming rule 1 does not fire at exactly adx=25 |

---

## Suggested Test Classes for `tests/test_signals.py`

| Class | Tests | Mocking |
|-------|-------|---------|
| `TestOutputSchema` | result is dict, has 3 keys {action, confidence, reason}, types correct | None |
| `TestBuyRule` | happy path, boundary adx=26, volume_ratio exactly 1.5, high ATR penalty | None |
| `TestSellRule` | happy path, negative momentum, high ATR penalty | None |
| `TestWatchlistRule` | happy path, adx=25 boundary (not > 25), adx=20 lower boundary | None |
| `TestHoldRule` | adx < 20, no volume confirmation, momentum=0.0 | None |
| `TestAtrModifier` | ATR exactly 5.0 (no penalty), ATR > 5.0 (penalty), ATR None (invalid) | None |
| `TestPreflightGuard` | each of the 4 params individually None → confidence 0.0; negative adx; adx > 100; non-numeric string; NaN/infinity | None |

---

## Dependencies

- `data/signals.py` has **no imports from other `data/` modules** — self-contained
- `import math` is the only import (same as `screener.py`)
- `tests/test_signals.py` imports `generate_advanced_signal` from `data.signals` only
- **No changes to any existing module** — `meta_agent.py`, `parallel_runner.py`, `screener.py` all unchanged
- Future story required to wire `generate_advanced_signal` into `parallel_runner._run_technical_agent` as an alternative or supplement to `generate_recommendation`
