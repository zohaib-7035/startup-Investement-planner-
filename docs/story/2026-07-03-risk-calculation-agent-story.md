# User Story: Risk Calculation Agent

Date: 2026-07-03
Source: Pasted text

---

## Story 15: Calculate Portfolio Risk Metrics

**As a** quantitative analyst using the stock intelligence platform,
**I want** to pass portfolio weights and historical return data and receive a comprehensive risk report (1-week 95% VaR, CVaR, portfolio volatility, and concentration risk),
**So that** I can assess portfolio downside exposure and receive actionable risk warnings before making allocation decisions.

### Scope In
- New module `data/risk.py` exposing one public function `calculate_risk_metrics(weights, returns_data, confidence_level=0.95, horizon_days=5)`
- Historical simulation VaR: compute daily portfolio P&L series from weighted returns, then take the `(1 - confidence_level)` percentile
- CVaR (Expected Shortfall): mean of all portfolio losses beyond the VaR threshold
- Portfolio volatility: annualised standard deviation of the weighted portfolio return series (×√252)
- Concentration risk: Herfindahl–Hirschman Index (HHI) of the weight vector (∑w²); higher = more concentrated
- Risk level classification: "Low" / "Medium" / "High" / "Critical" derived from VaR magnitude and concentration
- Warnings list: human-readable strings flagging breached thresholds (e.g. concentration > 0.40, VaR > 5%, single-asset portfolio)
- Return value is a plain Python dict with all-native types (float/str/list) — no numpy scalars
- Module-level `_EMPTY_RESULT` constant; outer `try/except` → `_EMPTY_RESULT.copy()` on any failure; never raises

### Scope Out
- Portfolio construction or weight optimisation (already in `data/portfolio.py`)
- Parametric / variance-covariance VaR (historical simulation only in this story)
- Monte Carlo simulation
- Multi-horizon VaR (horizon other than 1-week / 5 trading days)
- Per-asset individual VaR decomposition
- Persistence or reporting of results

### Acceptance Criteria

- **Given** a valid weights dict and a returns dict with ≥ 30 daily return rows per ticker, **when** `calculate_risk_metrics` is called, **then** it returns a dict with keys `var_1w_95`, `cvar_1w_95`, `portfolio_volatility`, `concentration_risk`, `risk_level`, `warnings` — all present and not None.

- **Given** a weights dict and returns data, **when** the function computes VaR, **then** it aligns tickers between weights and returns via inner-join on dates, computes the weighted daily portfolio return series, and returns 1-week VaR as `var_1w_95 = abs(percentile_5) × √5` (expressed as a positive loss fraction).

- **Given** the portfolio return series, **when** CVaR is computed, **then** `cvar_1w_95` equals the mean of all daily returns that are ≤ the VaR threshold multiplied by `√5`, expressed as a positive fraction.

- **Given** a weight vector where one asset holds ≥ 0.60 of the portfolio, **when** concentration risk is computed, **then** `concentration_risk` (HHI) exceeds 0.40 AND `warnings` includes a string containing "concentration".

- **Given** a `var_1w_95` exceeding 0.05 (5%), **when** risk level is classified, **then** `risk_level` is `"High"` or `"Critical"` AND `warnings` includes a string containing "VaR".

- **Given** invalid or missing inputs (None weights, empty returns dict, mismatched tickers, fewer than 2 aligned date rows), **when** the function is called, **then** it returns `_EMPTY_RESULT.copy()` (`var_1w_95=None`, etc.) and does not raise any exception.

- **Given** a single-ticker portfolio, **when** the function executes, **then** `concentration_risk == 1.0`, `warnings` includes a string containing "single asset", and all numeric outputs are Python-native `float`, not numpy scalars.

### Definition of Done
- [ ] `data/risk.py` implemented with `calculate_risk_metrics()` and `_EMPTY_RESULT` constant
- [ ] All values in return dict are Python-native types (`float`, `str`, `list`) — no numpy scalars
- [ ] `tests/test_risk.py` written; all tests pass
- [ ] `/test-review` run — Recommendation: Ready (no Meaningless tests, <25% Weak)
- [ ] `requirements.txt` updated if any new dependency added (numpy already present)
- [ ] No regression in existing 132 tests
