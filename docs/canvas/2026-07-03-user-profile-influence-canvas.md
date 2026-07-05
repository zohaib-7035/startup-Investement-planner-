# REASONS Canvas: User Profile Influence (Profile Advisor)
Date: 2026-07-03
Analysis: 2026-07-03-user-profile-influence-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The pipeline can generate a single BUY/SELL/HOLD signal for a stock, but has no mechanism to translate that signal into investor-specific guidance. A conservative investor and an aggressive investor should receive different position sizes and actions from the same market signal, especially when volatility is high.

**Goal:** Add `get_profile_recommendations` in a new `data/profile_advisor.py` module that takes a ticker label, a signal, and a volatility rating, then applies a formula-based rule engine to return per-profile position sizes, actions, and reasoning strings for each investor risk profile.

**Definition of Done:**
- [ ] Given `ticker="NVDA"`, `signal="BUY"`, `volatility="HIGH"`, and the three default profiles, when called, then a dict with exactly keys `"conservative"`, `"balanced"`, `"aggressive"` is returned, each mapping to `{action, position_size, reasoning}`
- [ ] Given BUY + HIGH, when computed, then conservative position_size equals 0.10 and action is "HOLD"; balanced equals 0.25 and action is "HOLD"; aggressive equals 0.45 and action is "BUY"
- [ ] Given BUY + LOW, when computed for aggressive profile, then position_size equals 0.9 and action is "BUY"
- [ ] Given SELL or HOLD signal with any volatility and any profile, when computed, then all profiles return position_size 0.0 and action "HOLD"
- [ ] Given a custom profiles list, when called, then only those profiles appear in the result
- [ ] Given an invalid signal string after normalisation, when called, then returns empty dict and never raises
- [ ] Given an invalid volatility string after normalisation, when called, then returns empty dict and never raises
- [ ] Given a profiles list where some entries are malformed, when called, then valid entries are returned and malformed entries are silently skipped; if all entries are invalid then returns empty dict
- [ ] Given any unhandled exception, when called, then returns empty dict and never raises

---

## E — Entities

### Data Contracts

| Name | Kind | Shape | Notes |
|------|------|-------|-------|
| `signal` input | str | one of "BUY", "SELL", "HOLD" (case-insensitive) | Normalised to uppercase on entry; accepts title-case from `screener.py` and all-caps from `meta_agent.py` |
| `volatility` input | str | one of "LOW", "MEDIUM", "HIGH" (case-insensitive) | Normalised to uppercase on entry |
| `profiles` input | list of dicts or None | each dict has `name (str)` and `risk_tol (float in [0,1])`; None triggers use of `_DEFAULT_PROFILES` | Malformed entries silently skipped by `_validate_profile` |
| `_EMPTY_PROFILES_RESULT` | module constant | `{}` — empty dict | Distinct from other modules' fixed-key fallbacks because output keys are caller-determined; always returned via `.copy()` |
| `_DEFAULT_PROFILES` | module constant | list of three dicts: Conservative/0.2, Balanced/0.5, Aggressive/0.9 | Read-only inside the function; never mutated |
| `_VOLATILITY_MODIFIERS` | module constant | dict mapping HIGH→0.5, MEDIUM→0.75, LOW→1.0 | Enables O(1) modifier lookup without if/elif chains |
| `_VALID_SIGNALS` | module constant | frozenset of "BUY", "SELL", "HOLD" | Used for pre-flight validation after case normalisation |
| `_BASE_SIZES` | module constant | dict mapping BUY→1.0, SELL→0.0, HOLD→0.0 | Long-only model: SELL means exit, not short |
| `_BUY_THRESHOLD` | module constant | 0.3 | position_size strictly greater than this → action is "BUY"; at or below → "HOLD" |
| per-profile result | dict per profile | `{action (str), position_size (float), reasoning (str)}` | position_size wrapped in `float()`; action is "BUY" or "HOLD" only |
| `get_profile_recommendations` return | dict | keyed by profile name string; value is the per-profile result dict | Empty dict `{}` on any failure |

### Dependencies on Existing Modules

| Module | Role | Notes |
|--------|------|-------|
| None | — | This module is fully self-contained; no imports from other `data/` modules |

---

## A — Approach

**Pattern:** Pure Python rule engine — single public function, two private helpers, all logic expressed as constant lookups and arithmetic.

**Strategy:** Model the module after `data/screener.py`: a thin public orchestrator that validates inputs up front, loops over profiles using `_validate_profile` to skip bad entries, applies the formula `base_size × volatility_modifier × risk_tol` per profile, derives action from the result against `_BUY_THRESHOLD`, and builds a reasoning string via `_build_reasoning`. All decision parameters live in module-level constants so there are no magic literals anywhere in the logic.

**Scope In:**
- Single-call, single-ticker, multi-profile recommendation generation
- Formula: `position_size = _BASE_SIZES[signal] × _VOLATILITY_MODIFIERS[volatility] × risk_tol`, clamped to [0.0, 1.0]
- Action derived from `position_size > _BUY_THRESHOLD`
- Per-profile reasoning string naming ticker, signal, volatility, risk tolerance, modifier, and resulting size
- Three built-in default profiles; custom profiles list overrides them completely
- Skip-invalid-per-item semantics for the profiles list
- Pre-flight rejection of invalid signal and volatility strings

**Scope Out:**
- Short-selling or negative position sizes
- Fetching any market data (price, RSI, EPS) inside this module
- Multi-ticker batch calls
- User persistence, authentication, or account management
- LLM-generated reasoning
- Dynamic modification of built-in profiles at runtime

---

## S — Structure

**Module path:** `Z:\claude\stock_analyzer\data\profile_advisor.py`

**New Files:**
- `data/profile_advisor.py` — entire new module: five module-level constants, two private helpers, one public function
- `tests/test_profile_advisor.py` — full test suite; no mocking required (pure function with no external calls)

**Modified Files:**
- None — no existing module needs to change

**New Dependencies:**
- None — pure Python stdlib only

---

## O — Operations

1. Create `data/profile_advisor.py` with all module-level constants: `_EMPTY_PROFILES_RESULT` as an empty dict; `_DEFAULT_PROFILES` as a list of three dicts each with `name` and `risk_tol` keys for Conservative at 0.2, Balanced at 0.5, and Aggressive at 0.9; `_VOLATILITY_MODIFIERS` as a dict mapping the three volatility strings to their float multipliers; `_VALID_SIGNALS` as a frozenset of the three valid uppercase signal strings; `_BASE_SIZES` as a dict mapping signal strings to their base float values where BUY maps to 1.0 and both SELL and HOLD map to 0.0; and `_BUY_THRESHOLD` as the float 0.3

2. Implement `_validate_profile(profile)` — accepts one item from the profiles list; returns a two-element tuple of name and risk_tol if the entry is valid, or None to signal skip; validation rules: entry must be a dict; `name` key must be present and its value must be a non-empty string; `risk_tol` key must be present and its value must be a numeric type that is not a bool and must be a float in the closed interval from 0.0 to 1.0 inclusive; use `float()` conversion to normalise int values; any failure returns None without raising

3. Implement `_build_reasoning(ticker, signal, volatility, risk_tol, modifier, position_size, action)` — returns a single human-readable string that states the ticker and signal received, the volatility level and its modifier value, the profile's risk tolerance, the computed position size, and the resulting action; the string must name all four inputs so a reader can verify the formula result without consulting the code

4. Implement `get_profile_recommendations(ticker, signal, volatility, profiles=None)` — normalise both signal and volatility to uppercase via str conversion immediately on entry; validate normalised signal against `_VALID_SIGNALS` and return `_EMPTY_PROFILES_RESULT.copy()` if invalid; look up the volatility modifier in `_VOLATILITY_MODIFIERS` and return `_EMPTY_PROFILES_RESULT.copy()` if not found; set the active profiles list to `_DEFAULT_PROFILES` when the argument is None, otherwise use the caller-supplied list; for each profile entry call `_validate_profile` and skip None results; compute `position_size` as `_BASE_SIZES[signal] × modifier × risk_tol` wrapped in `float()` and clamped to the closed interval [0.0, 1.0]; derive action as the string "BUY" when position_size is strictly greater than `_BUY_THRESHOLD`, otherwise "HOLD"; build the reasoning string via `_build_reasoning`; store the per-profile result dict under the profile name in the output dict; after the loop, if the output dict is empty return `_EMPTY_PROFILES_RESULT.copy()`; wrap the entire function body in a single outer try-except Exception that returns `_EMPTY_PROFILES_RESULT.copy()` on any unhandled error; never raise

5. Create `tests/test_profile_advisor.py` — no mocking is needed since the function is pure Python; cover the following test classes: OutputSchema (return dict has exactly three keys for default profiles; each per-profile dict has exactly the keys action, position_size, and reasoning; position_size is Python float not int; action is a string); FormulaVerification (BUY plus HIGH gives conservative position_size of exactly 0.10 and action HOLD; BUY plus HIGH gives balanced 0.25 and action HOLD; BUY plus HIGH gives aggressive 0.45 and action BUY; BUY plus LOW gives aggressive position_size exactly 0.9 and action BUY; BUY plus MEDIUM gives balanced exactly 0.375; conservative position_size is always less than or equal to balanced which is always less than or equal to aggressive for any BUY signal); SignalBehaviour (SELL signal gives position_size 0.0 and action HOLD for all profiles; HOLD signal gives position_size 0.0 and action HOLD for all profiles; title-case signal "Buy" is accepted and produces same result as "BUY"; lowercase signal "buy" is accepted; mixed-case volatility "high" is accepted); ThresholdBoundary (position_size of exactly 0.3 produces action HOLD not BUY; position_size just above 0.3 produces action BUY; risk_tol of 0.0 produces position_size 0.0 for any signal; risk_tol of 1.0 with BUY and LOW produces position_size 1.0); CustomProfiles (single custom profile appears as the only key in result; custom profile with risk_tol 0.05 and BUY plus HIGH produces correct position_size); PreflightGuards (unknown signal returns empty dict; unknown volatility returns empty dict; profiles list with all invalid entries returns empty dict; profiles list with one valid and one invalid entry returns only the valid profile; profile with missing name key is skipped; profile with risk_tol above 1.0 is skipped; profile with risk_tol below 0.0 is skipped; non-dict profile entry is skipped)

---

## N — Norms

### Python Pipeline Norms

- Every public function has a single outer `try/except Exception` boundary — it never raises to the caller
- Return dicts use Python-native types only — wrap all computed floats with `float()`
- Module-level constants for all decision parameters — no magic literals inside function bodies
- `_EMPTY_PROFILES_RESULT` is an empty dict `{}`; always return `.copy()` — never return the constant itself
- Private helpers are prefixed with underscore; the public function is a thin orchestrator
- No imports from other `data/` modules — this module is fully self-contained
- No external HTTP calls, no LLM calls, no numpy — pure Python stdlib only
- Python 3.9 compatibility — no bare `X | Y` union type hints in function signatures

---

## S — Safeguards

### General Pipeline Safeguards

- Never raise an exception to the caller — all error paths return `_EMPTY_PROFILES_RESULT.copy()`
- Never mutate `_EMPTY_PROFILES_RESULT`, `_DEFAULT_PROFILES`, `_VOLATILITY_MODIFIERS`, `_VALID_SIGNALS`, `_BASE_SIZES`, or `_BUY_THRESHOLD` at runtime — all are read-only constants
- Never return a non-float position_size — always wrap the computed value with `float()`
- Do not import private helpers from other `data/` modules

### Feature-Specific Safeguards

- Normalise `signal` and `volatility` to uppercase before any validation — both title-case and all-caps inputs from upstream modules must be accepted
- `_validate_profile` must reject bool values for `risk_tol` explicitly — in Python, `bool` is a subclass of `int`, so `isinstance(True, (int, float))` is True; add a `isinstance(risk_tol, bool)` guard before the numeric check
- The position_size formula result must be clamped to [0.0, 1.0] — floating-point arithmetic with `risk_tol=1.0` and exact modifier values could theoretically produce values slightly above 1.0
- After the per-profile loop, check whether the result dict is empty before returning — if every profile was invalid, return `_EMPTY_PROFILES_RESULT.copy()` not the empty accumulator dict (they are identical in value but this makes the intent explicit)
- `ticker` must be coerced to string before use in the reasoning string — do not validate or reject non-string ticker values; use `str(ticker)` silently

---

## Change Log

- 2026-07-03: Initial canvas generated from analysis `2026-07-03-user-profile-influence-analysis.md`
