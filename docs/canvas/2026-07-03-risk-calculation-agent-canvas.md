# REASONS Canvas: Risk Calculation Agent

Date: 2026-07-03
Analysis: docs/analysis/2026-07-03-risk-calculation-agent-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The platform can optimise a portfolio but has no way to quantify downside exposure. An analyst who receives optimised weights has no signal about how much capital is at risk, how concentrated the position is, or when to be alarmed.

**Goal:** A new pure-Python module `data/risk.py` that accepts portfolio weights and pre-fetched historical price data and returns a 6-key risk report — 1-week 95% VaR, CVaR, annualised volatility, HHI concentration, risk level classification, and a human-readable warnings list — with no external calls and no raised exceptions.

**Definition of Done:**
- [ ] Given a valid weights dict and returns data with at least 30 daily price rows per ticker, when `calculate_risk_metrics` is called, then the result has exactly 6 keys: `var_1w_95`, `cvar_1w_95`, `portfolio_volatility`, `concentration_risk`, `risk_level`, `warnings` — all non-None.
- [ ] Given a weights dict and returns data, when VaR is computed, then dates are inner-joined across tickers, a weighted daily log-return series is produced, and `var_1w_95` equals the absolute value of the 5th percentile of that series scaled by the square root of 5.
- [ ] Given the portfolio return series, when CVaR is computed, then `cvar_1w_95` equals the mean of all daily returns at or below the negative of the daily VaR, scaled by the square root of 5.
- [ ] Given a weight vector where one asset holds 60 percent or more, when concentration is computed, then `concentration_risk` exceeds 0.40 and `warnings` contains a string with the word "concentration".
- [ ] Given a `var_1w_95` exceeding 0.05, when risk level is classified, then `risk_level` is "High" or "Critical" and `warnings` contains a string with the word "VaR".
- [ ] Given invalid or missing inputs (None weights, empty returns dict, mismatched tickers, fewer than 2 aligned date rows), when the function is called, then `_EMPTY_RESULT.copy()` is returned and no exception is raised.
- [ ] Given a single-ticker portfolio, when the function executes, then `concentration_risk` is exactly 1.0, `warnings` contains the phrase "single asset", and every numeric output is a Python-native float.

---

## E — Entities

### Data Contracts

| Name | Kind | Shape | Notes |
|------|------|-------|-------|
| `weights` | Input parameter | dict mapping ticker string to float weight | Weights need not sum to 1.0 before input; surviving weights are re-normalised internally |
| `returns_data` | Input parameter | dict mapping ticker string to a list of dicts, each dict having at least a `date` string and a `close` float | Same shape as `get_stock_history()` output — no transformation needed by the caller |
| `_EMPTY_RESULT` | Module-level constant | dict with 6 keys: `var_1w_95`, `cvar_1w_95`, `portfolio_volatility`, `concentration_risk`, `risk_level`, `warnings` — all set to None | Returned via `.copy()` on any failure |
| `_RISK_THRESHOLDS` | Module-level constant | Ordered list of tuples, each holding a VaR threshold, a concentration threshold, and a risk label string — checked from highest severity to lowest | Critical first, then High, Medium; Low is the final fallback |
| Result dict | Output | Same 6 keys as `_EMPTY_RESULT` with real values: four Python floats, one string, one list of strings | All floats wrapped with `float()` to prevent numpy scalar leakage |

### Private Helper Contracts

| Helper | Input | Output | Responsibility |
|--------|-------|--------|----------------|
| `_build_portfolio_series` | `weights` dict, `returns_data` dict | numpy array of daily portfolio log-returns, or None | Inner-joins dates, extracts close prices, computes log returns, re-normalises surviving weights, applies weighted dot product |
| `_compute_var_cvar` | portfolio return series, confidence level float, horizon days int | tuple of (var_1w float, cvar_1w float) | Computes daily VaR via percentile, CVaR as tail mean (defaulting to VaR if tail is empty), scales both by sqrt of horizon days |
| `_compute_concentration` | `weights` dict | HHI float | Sum of squared weights; produces 1.0 for a single-asset portfolio |
| `_classify_risk_level` | var_1w float, concentration float | risk label string | Checks `_RISK_THRESHOLDS` in order from Critical downward; returns first matching label |
| `_build_warnings` | var_1w float, concentration float, n_tickers int | list of strings | Appends a warning for single-asset, for concentration above 0.40, and for VaR above 0.05 |

---

## A — Approach

**Pattern:** Pure computation module following the screener and graph-reasoning pattern — input validation, inner-join alignment, numpy array operations, threshold classification, exception boundary.

**Strategy:** `calculate_risk_metrics` receives pre-fetched price data in the same dict-list format as `get_stock_history()`, so it makes no external calls and requires no mocking in tests. The computation flows through five independent private helpers in a strict pipeline order: build the weighted return series first, then derive VaR and CVaR from it, compute concentration from weights alone, classify risk level from the two numeric outputs, and finally build the warnings list. All numpy intermediate values are converted to Python-native floats before being placed in the return dict, following the same `float()` wrapping pattern established in `_compute_stats` in `portfolio.py`.

**Scope In:**
- `data/risk.py` with one public function and five private helpers
- Historical simulation VaR and CVaR at the 95% confidence level scaled to 1 week by the square-root-of-time rule
- Annualised portfolio volatility from the weighted daily log-return series
- HHI-based concentration risk
- Ordered threshold classification into Low, Medium, High, or Critical
- Human-readable warnings list
- `tests/test_risk.py` covering all seven acceptance criteria plus edge cases

**Scope Out:**
- Parametric or Monte Carlo VaR methods
- Multi-horizon VaR beyond the default 5-day window
- Per-asset VaR decomposition
- Any call to `get_stock_history()` inside `data/risk.py` — the caller is responsible for fetching
- Persistence, reporting, or display of results

---

## S — Structure

**Module:** `data/risk.py` (new file)

**New Files:**
- `data/risk.py` — single public function `calculate_risk_metrics` with five private helpers and two module-level constants
- `tests/test_risk.py` — pure-Python test suite, no mocking

**Modified Files:**
- None — no existing module is changed

**Database:** None — no persistence, no migration

---

## O — Operations

1. Create `data/risk.py` with imports of `math` and `numpy`, define `_EMPTY_RESULT` as a module-level dict constant with six keys all set to None, and define `_RISK_THRESHOLDS` as an ordered list of three tuples where each tuple holds a VaR threshold float, a concentration threshold float, and a label string — ordered Critical, High, Medium (Low is the implied final fallback requiring no tuple).

2. Implement `_build_portfolio_series(weights, returns_data)` as a private function that takes a weights dict and a returns_data dict, identifies tickers present in both, inner-joins their price lists on the `date` field to find common dates, builds a 2-D numpy array of close prices, computes log returns row-by-row using numpy.log of the ratio of consecutive rows, re-normalises the surviving weights so they sum to 1.0, applies the normalised weight vector via dot product to produce a 1-D daily portfolio return array, and returns that array — or returns None if there are fewer than 2 aligned date rows or no surviving tickers.

3. Implement `_compute_var_cvar(portfolio_series, confidence_level, horizon_days)` as a private function that computes the daily VaR as the absolute value of numpy.percentile of the series at the (1 minus confidence_level) times 100 quantile, computes the CVaR tail as the absolute value of the mean of all series values at or below the negative of the daily VaR (defaulting to the daily VaR if the tail mask selects no values), scales both by math.sqrt(horizon_days), and returns them as a tuple of two Python floats.

4. Implement `_compute_concentration(weights)` as a private function that computes the sum of squared values of the weights dict and returns it as a Python float; a single-key weights dict naturally produces 1.0.

5. Implement `_classify_risk_level(var_1w, concentration)` as a private function that iterates through `_RISK_THRESHOLDS` in order and returns the label of the first tuple whose VaR threshold or concentration threshold is met or exceeded; returns the string "Low" if no tuple matches.

6. Implement `_build_warnings(var_1w, concentration, n_tickers)` as a private function that builds a list of strings: appends a "single asset portfolio" warning if n_tickers equals 1, appends a "concentration" warning including the numeric HHI value if concentration exceeds 0.40, and appends a "VaR" warning including the percentage value if var_1w exceeds 0.05; returns the list, which may be empty.

7. Implement `calculate_risk_metrics(weights, returns_data, confidence_level=0.95, horizon_days=5)` as the public entry point: validate that weights is a non-empty dict, returns_data is a non-empty dict, confidence_level is a float strictly between 0 and 1, and horizon_days is a positive numeric value — returning `_EMPTY_RESULT.copy()` on any validation failure; call `_build_portfolio_series` and return `_EMPTY_RESULT.copy()` if it returns None; call `_compute_var_cvar`, `_compute_concentration`; compute portfolio_volatility as float(numpy.std(series, ddof=1) times math.sqrt(252)); call `_classify_risk_level` and `_build_warnings`; assemble the 6-key result dict with all values cast to Python-native types; wrap the entire function body in a try-except that returns `_EMPTY_RESULT.copy()` on any unhandled exception.

8. Create `tests/test_risk.py`: define a module-level `_make_returns_data(prices_by_ticker, start_date)` fixture function that builds a dict of ticker to list-of-dicts matching the `get_stock_history()` shape; write a `TestCalculateRiskMetricsSchema` class verifying the 6-key dict shape and that all fields are non-None on valid input; write a `TestVaRAndCVaR` class verifying VaR is positive, CVaR is at least as large as VaR, and both are Python floats; write a `TestConcentration` class verifying HHI equals 1.0 for a single-ticker portfolio and the "single asset" warning fires; write a `TestRiskLevelClassification` class verifying each of the four labels fires at the correct threshold boundary; write a `TestWarnings` class verifying the concentration warning fires when HHI exceeds 0.40 and the VaR warning fires when VaR exceeds 0.05; write a `TestEdgeCases` class verifying that None weights, empty returns_data, fully mismatched tickers, fewer than 2 aligned rows, and a flat price series all return `_EMPTY_RESULT.copy()` without raising; write a `TestTypeSafety` class verifying that `var_1w_95`, `cvar_1w_95`, `portfolio_volatility`, and `concentration_risk` are all instances of Python built-in float, not numpy types.

---

## N — Norms

### Python Data Pipeline Norms

- One public function per module; private helpers are prefixed with underscore
- Every public function has a single outer try-except Exception boundary — it never raises to its caller
- All values in the return dict use Python-native types only — float, str, list — never numpy scalars, numpy arrays, or pandas types
- Module-level fallback dicts are defined as constants; always return `.copy()`, never the constant itself
- Input validation happens before computation; invalid inputs return the fallback dict, they do not raise
- Private helpers may raise; the public function's outer try-except catches them
- Tests for pure-Python functions use no mocking — call the function directly with constructed fixtures
- Test method naming follows `test_<what>_<condition>` (for example, `test_var_is_positive_on_valid_input`)
- Assert the primary output fields on every happy-path test
- Use `assertIs(type(value), float)` not `assertIsInstance` when verifying Python-native float
- Python 3.9 compatibility: use string annotations for union types (`"float | None"`)

---

## S — Safeguards

### General Safeguards

- The public function must never raise — the outer try-except must cover the entire function body including input validation
- No numpy scalar may appear in the return dict — every numeric field must pass through `float()` before being set
- CVaR must never be less than VaR — if the tail mask selects no values, fall back to VaR as CVaR
- Surviving weights must be re-normalised to sum to 1.0 before the weighted dot product — never assume the caller's weights are already normalised
- Fewer than 2 aligned date rows after inner-join must return `_EMPTY_RESULT.copy()`, not proceed to computation
- An empty `warnings` list is a valid result — do not return None for this field
- `_EMPTY_RESULT` must be a module-level constant, never constructed inside a function call — always return `.copy()` of it

### Feature-Specific Safeguards

- Tickers present in weights but absent from returns_data are silently dropped by the inner-join; re-normalise the surviving weights immediately after filtering to prevent an under-weighted portfolio series
- A perfectly flat close-price series produces VaR = 0.0 and CVaR = 0.0 — this is valid output and must not cause a division-by-zero error
- `confidence_level` outside the open interval (0, 1) must return `_EMPTY_RESULT.copy()` — both 0.0 and 1.0 are invalid
- `horizon_days` that is zero, negative, or non-numeric must return `_EMPTY_RESULT.copy()`

---

## Change Log

*(appended by /sync)*
