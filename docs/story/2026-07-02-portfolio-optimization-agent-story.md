# User Story: Portfolio Optimization Agent
Date: 2026-07-02
Source: Pasted text

---

## Story 14: Markowitz Portfolio Optimization

**As a** system (automated pipeline consumer),
**I want** to call a single function with a list of tickers, a risk tolerance value, and an investment horizon in years and receive optimal portfolio weights alongside expected return, volatility, and Sharpe ratio,
**So that** downstream agents or UIs can present quantitatively grounded allocation recommendations without reimplementing mean-variance math.

### What Is Already Done
- `get_stock_history(ticker, start, end)` in `data/stock.py` returns sorted OHLCV dicts — the price data source this story builds on.
- `get_fundamentals(ticker)` exposes EPS and PE ratio per ticker — available for enrichment if needed.
- All pipeline modules follow the no-raise, native-type-only, `_EMPTY.copy()` fallback convention.

### What Is Remaining (this story)
- New module `data/portfolio.py` with public function `optimize_portfolio(tickers, risk_tolerance, horizon_years)`.
- Fetch `horizon_years × 252` trading days of daily close prices for each ticker via `get_stock_history`.
- Compute annualised expected returns (mean log-return × 252) and covariance matrix (annualised).
- Run Markowitz mean-variance optimisation via `scipy.optimize.minimize` (SLSQP) subject to: weights sum to 1, all weights ≥ 0, and a risk constraint derived from `risk_tolerance`.
- Return a 4-key result dict. Add `scipy` to `requirements.txt`.
- Tests in `tests/test_portfolio.py` — all `get_stock_history` calls mocked.

### Scope In
- `optimize_portfolio(tickers, risk_tolerance, horizon_years)` — single public function, one module.
- Long-only portfolio (weights ≥ 0, sum to 1).
- Risk tolerance interpreted as a scalar weight on the variance penalty (0 = max return focus, 1 = min variance focus).
- Sharpe ratio computed using a fixed risk-free rate of 0.0 (can be parameterised in a future story).
- Returns Python-native floats only — no numpy scalars in the output dict.

### Scope Out
- No short-selling or leverage (weights can be 0 but not negative).
- No sector/concentration constraints beyond the basic simplex.
- No persistent storage of results — function is stateless.
- No CLI or HTTP endpoint — pure function contract only.
- Risk-free rate parameterisation deferred to a future story.
- Black-Litterman or other alternative optimisers deferred.

### Acceptance Criteria

**Happy path:**
- Given tickers `["AAPL","MSFT","NVDA","GOOGL"]`, risk_tolerance `0.5`, horizon_years `5`, when `optimize_portfolio` is called with mocked price history, then the result contains keys `weights`, `expected_return`, `volatility`, `sharpe_ratio`.
- Given the same inputs, then `sum(result["weights"].values())` is within 1e-6 of 1.0 and all individual weights are ≥ 0.0.
- Given the same inputs, then `result["expected_return"]`, `result["volatility"]`, and `result["sharpe_ratio"]` are Python `float` values (not numpy scalars).

**Diversification:**
- Given risk_tolerance `0.0` (pure return maximisation) with clearly differentiated mocked returns, then the optimizer is not required to diversify — single-asset concentration is valid.
- Given risk_tolerance `1.0` (pure variance minimisation) with identical mocked returns, then weights are approximately equal (max diversification).

**Edge cases / fallbacks:**
- Given an empty tickers list `[]`, then `optimize_portfolio` returns `_EMPTY_PORTFOLIO` (all-None) without raising.
- Given a single ticker, then the result assigns `{"AAPL": 1.0}` weight and computes return/volatility/sharpe from that single asset's history.
- Given any ticker for which `get_stock_history` returns `[]` (network failure), then that ticker is silently dropped; if all tickers fail, `_EMPTY_PORTFOLIO` is returned.
- Given `risk_tolerance` outside `[0, 1]` (e.g. `-0.1` or `1.5`), then it is clamped to `[0, 1]` before use — no raise.
- Given `horizon_years` ≤ 0 or non-numeric, then `_EMPTY_PORTFOLIO` is returned.
- Given fewer than 2 trading-day observations per ticker after fetching (degenerate history), then `_EMPTY_PORTFOLIO` is returned.

**Schema / type contract:**
- `result["weights"]` is `dict[str, float]` keyed by ticker symbol — never a list, never numpy.
- `result["expected_return"]` and `result["volatility"]` are annualised figures (not daily).
- Function never raises under any input.

### Definition of Done
- [ ] `data/portfolio.py` implemented with `optimize_portfolio` and `_EMPTY_PORTFOLIO` constant
- [ ] `scipy` added to `requirements.txt`
- [ ] `tests/test_portfolio.py` written — `get_stock_history` mocked, no real HTTP calls
- [ ] All new tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_portfolio.py -v`
- [ ] Full suite still green: `& "Z:\python39\python.exe" -m pytest tests/ -v` (112 + new tests passing)
- [ ] `/test-review` run — Recommendation: Ready (no Meaningless, <25% Weak)
- [ ] Memory updated: architecture, completed stories, requirements
