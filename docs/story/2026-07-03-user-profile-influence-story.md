# User Story: User Profile Influence (Profile Advisor)
Date: 2026-07-03
Source: Pasted text — Story 19: User Profile Influence

---

## Story 19: Generate Profile-Adjusted Investment Recommendations

**As a** quantitative analyst using the AI Stock Intelligence Platform,
**I want** to apply investor risk profiles to a stock signal and volatility rating to produce per-profile recommendations,
**So that** the same market signal is correctly sized and labelled for conservative, balanced, and aggressive investors rather than returning a one-size-fits-all action.

### Scope In
- Single function `get_profile_recommendations(ticker, signal, volatility, profiles=None)` in `data/profile_advisor.py`
- `signal`: one of `"BUY"` / `"SELL"` / `"HOLD"` (case-insensitive normalisation)
- `volatility`: one of `"LOW"` / `"MEDIUM"` / `"HIGH"` (case-insensitive normalisation)
- `profiles`: optional `list[dict]` each with `{name: str, risk_tol: float}`; defaults to three built-in profiles — Conservative (0.2), Balanced (0.5), Aggressive (0.9)
- `ticker`: string label passed through to reasoning strings; not validated or fetched
- Return value: `dict[str, dict]` keyed by profile name, each value having keys `action`, `position_size`, `reasoning`
- `position_size`: float in `[0.0, 1.0]` — fraction of available capital to deploy; 0.0 means no position
- `action`: derived from `position_size` — `"BUY"` if `position_size > 0.3`, `"HOLD"` otherwise (long-only model; no short selling)
- Volatility modifier: `HIGH` → multiply base size by `0.5`; `MEDIUM` → multiply by `0.75`; `LOW` → multiply by `1.0`
- Base size from signal: `BUY` → `1.0`; `SELL` → `0.0` (long-only: sell = exit, not short); `HOLD` → `0.0`
- Final `position_size` = `base_size × volatility_modifier × risk_tol`, clamped to `[0.0, 1.0]`
- `_EMPTY_PROFILES_RESULT`: module-level fallback constant — empty dict `{}`; returned via `.copy()` on any failure
- Pure Python stdlib only — no LLM, no external calls, no numpy

### Scope Out
- Short-selling or negative position sizes
- Fetching price, RSI, EPS, or any real market data inside this module
- Multi-ticker or portfolio-level profile recommendations in a single call
- User authentication or user-account persistence
- UI or API layer
- Dynamic profile creation (profiles are passed in or use built-in defaults)

### Acceptance Criteria

- **Given** `ticker="NVDA"`, `signal="BUY"`, `volatility="HIGH"`, and the three default profiles,
  **when** `get_profile_recommendations` is called,
  **then** it returns a dict with exactly three keys (`"conservative"`, `"balanced"`, `"aggressive"`), each mapping to a dict with keys `action`, `position_size`, and `reasoning`.

- **Given** a `BUY` signal and `HIGH` volatility,
  **when** recommendations are computed,
  **then** `position_size` for conservative ≤ `position_size` for balanced ≤ `position_size` for aggressive; and `action` for conservative is `"HOLD"` (since `1.0 × 0.5 × 0.2 = 0.10 ≤ 0.3` threshold).

- **Given** a `BUY` signal and `LOW` volatility,
  **when** recommendations are computed for an aggressive profile (risk_tol=0.9),
  **then** `position_size` equals `0.9` (1.0 × 1.0 × 0.9) and `action` is `"BUY"`.

- **Given** a `SELL` or `HOLD` signal (any volatility, any profile),
  **when** recommendations are computed,
  **then** `position_size` is `0.0` and `action` is `"HOLD"` for all profiles (long-only model).

- **Given** a custom profiles list `[{"name": "ultra_safe", "risk_tol": 0.05}]`,
  **when** `get_profile_recommendations` is called,
  **then** only the key `"ultra_safe"` appears in the result, and its `position_size` reflects `risk_tol=0.05`.

- **Given** `signal` is not one of `BUY`, `SELL`, or `HOLD` (after case normalisation),
  **when** `get_profile_recommendations` is called,
  **then** it returns `_EMPTY_PROFILES_RESULT.copy()` and never raises.

- **Given** `volatility` is not one of `LOW`, `MEDIUM`, or `HIGH` (after case normalisation),
  **when** `get_profile_recommendations` is called,
  **then** it returns `_EMPTY_PROFILES_RESULT.copy()` and never raises.

- **Given** a profile dict in the `profiles` list that is missing `name` or `risk_tol`, or has `risk_tol` outside `[0.0, 1.0]`,
  **when** `get_profile_recommendations` is called,
  **then** that profile is silently skipped; valid profiles are still computed; if all profiles are invalid, returns `_EMPTY_PROFILES_RESULT.copy()`.

- **Given** any unexpected exception occurs during computation,
  **when** `get_profile_recommendations` is called,
  **then** it returns `_EMPTY_PROFILES_RESULT.copy()` and never raises.

### Definition of Done
- [ ] `data/profile_advisor.py` implemented with `get_profile_recommendations` matching the contract above
- [ ] `_EMPTY_PROFILES_RESULT = {}` module-level constant; always `.copy()` on return
- [ ] `_DEFAULT_PROFILES` module-level constant with three built-in profile dicts
- [ ] `_VOLATILITY_MODIFIERS` and `_VALID_SIGNALS` module-level constants — no magic inline literals
- [ ] All output `position_size` values wrapped with `float()` — no implicit precision issues
- [ ] `tests/test_profile_advisor.py` written with no real HTTP calls (pure function — no mocking needed)
- [ ] All tests passing with `& "Z:\python39\python.exe" -m pytest tests/test_profile_advisor.py -v`
- [ ] Full suite still green: `& "Z:\python39\python.exe" -m pytest tests/ -v`
- [ ] `/test-review` run; Recommendation: Ready (no Meaningless, <25% Weak)

---
