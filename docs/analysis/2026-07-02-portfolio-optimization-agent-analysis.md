# Analysis: Portfolio Optimization Agent
Date: 2026-07-02
Story: 2026-07-02-portfolio-optimization-agent-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9 data pipeline — no web framework, no ORM, no persistence layer. 12 modules in `data/`, each exposing one or two public functions. Key libraries already installed: `yfinance==0.2.66`, `numpy==1.26.4`, `pandas==2.2.2`. **`scipy` is not in `requirements.txt`** — it must be added before the optimizer can run. All modules follow three shared conventions: a module-level `_EMPTY_X` fallback constant returned via `.copy()`, a `_safe_float` helper that normalises numpy scalars, and an outer `try/except Exception → fallback` boundary that prevents any public function from raising.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---|---|---|
| `get_stock_history(ticker, start, end)` | `data/stock.py:7` | Returns `list[dict]` with `date, open, high, low, close, volume` — daily OHLCV sorted ascending. Returns `[]` on any failure. This is the sole price data source for portfolio construction. |
| `_safe_float(value)` | `data/stock.py:66` | Converts numpy/pandas scalars to Python `float | None`. Same pattern must be applied to every value in the output dict of `optimize_portfolio`. |
| `_INVALID_RSI_FALLBACK` / `_EMPTY_DATASET` pattern | `data/screener.py:5`, `data/openbb_client.py` | Module-level constant, returned via `.copy()`. The new `_EMPTY_PORTFOLIO` follows the same idiom. |
| `numpy==1.26.4` | `requirements.txt:3` | Already installed — available for log-return and covariance matrix computation. |
| `pandas==2.2.2` | `requirements.txt:2` | Already installed — can be used for date-aligned price DataFrame construction, but must not leak into the output dict. |

### Missing — Needs to Be Added

| Concept | Type | Notes |
|---|---|---|
| `data/portfolio.py` | New Python module | Does not exist. Contains `optimize_portfolio`, `_EMPTY_PORTFOLIO`, `_safe_float` (copied locally), `_build_price_matrix`, `_compute_stats`. |
| `optimize_portfolio(tickers, risk_tolerance, horizon_years)` | Public function | Core function — fetches prices, runs Markowitz SLSQP, returns 4-key dict. |
| `_EMPTY_PORTFOLIO` | Module-level constant | `{"weights": None, "expected_return": None, "volatility": None, "sharpe_ratio": None}` — all-None fallback. |
| `_build_price_matrix(tickers, start, end)` | Private helper | Calls `get_stock_history` per ticker, extracts close prices, aligns by date (inner join), returns a 2D numpy array of shape `(n_days, n_tickers)` and the aligned ticker list. Returns `(None, [])` if fewer than 2 observations survive alignment. |
| `_compute_stats(weights, mean_returns, cov_matrix)` | Private helper | Computes portfolio return (`w · μ`), volatility (`√(wᵀΣw)`), Sharpe (`return / volatility`). All inputs and outputs are Python `float`. |
| `scipy` | New dependency | `scipy.optimize.minimize` with `method="SLSQP"` is the optimizer. Not in `requirements.txt` — must be added as `scipy>=1.11`. |
| `tests/test_portfolio.py` | New test file | All `get_stock_history` calls patched via `@patch("data.portfolio.get_stock_history")`. No real HTTP calls. |

---

## Strategic Approach

Fetch close prices for each ticker by calling `get_stock_history` with a computed date window (`today − horizon_years × 365` to `today`), then align all tickers to their common trading dates (inner join) so the covariance matrix is consistent. Compute log returns (`np.log(p[1:]/p[:-1])`), annualise mean and covariance by ×252. Pass these to `scipy.optimize.minimize(method="SLSQP")` with a weighted objective `(1 - risk_tolerance) × (−portfolio_return) + risk_tolerance × portfolio_variance` — this single scalar trades off return maximisation vs. variance minimisation continuously across `[0,1]`. All numpy scalars in the result are wrapped with `float()` before the dict is returned. The outer `try/except Exception → _EMPTY_PORTFOLIO.copy()` is the last line of defence.

---

## Key Design Decisions

- **`scipy.optimize.minimize` over manual efficient-frontier sweep** — SLSQP solves the constrained quadratic in one call; sweeping the frontier is unnecessary for a single risk-tolerance input.
- **Log returns over simple returns** — log returns are time-additive and more statistically stable for multi-year windows; consistent with quantitative finance convention.
- **Inner join on dates, not union** — missing data for one ticker on a day would contaminate the covariance matrix; inner join gives a clean, balanced panel.
- **risk_tolerance clamp before use, not validation** — `max(0.0, min(1.0, float(risk_tolerance)))` keeps the function forgiving; only structurally invalid inputs (non-numeric) fall back to `_EMPTY_PORTFOLIO`.
- **`_safe_float` copied locally** — consistent with `openbb_client.py` pattern; no cross-module imports inside `data/`.
- **Single-ticker shortcut** — with one ticker, SLSQP would be trivial but adds import overhead; handle directly: `weight = 1.0`, compute stats from that ticker's returns only.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|---|---|---|
| `scipy` not installed | High | Not in `requirements.txt`. Must add `scipy>=1.11` before any test can run. |
| Numpy scalar leakage in output | High | `scipy` returns numpy float64 for objective values; weights from `result.x` are also numpy arrays. Every value must be passed through `float()`. |
| Degenerate covariance matrix (near-singular) | Medium | Highly correlated assets or very short windows can make the covariance matrix non-invertible. SLSQP may still converge, but if it doesn't (`result.success == False`), return `_EMPTY_PORTFOLIO`. |
| Date misalignment across tickers | Medium | AAPL and NVDA trade the same days, but international tickers or new listings may have gaps. Inner join silently drops days with any missing ticker — if result has fewer than 2 rows, return `_EMPTY_PORTFOLIO`. |
| All tickers return `[]` from `get_stock_history` | Medium | Network failure scenario. After dropping failed tickers, zero tickers remain → `_EMPTY_PORTFOLIO`. |
| `horizon_years` × 252 exceeds available history | Low | yfinance caps free data; fewer observations returned than requested. Proceed with what's available (≥2 rows), or fall back. |
| `math.isfinite` check on Sharpe ratio | Low | If `volatility == 0.0` (flat price history), division by zero produces `inf`. Must guard: `sharpe = float(port_return / port_vol) if port_vol > 0 else 0.0`. |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|---|---|---|
| Result has keys `weights, expected_return, volatility, sharpe_ratio` | Needs work | Defined in new `_EMPTY_PORTFOLIO` shape; populated by `optimize_portfolio`. |
| `sum(weights.values())` within 1e-6 of 1.0 | Needs work | Enforced by SLSQP equality constraint `{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}`. |
| All weights ≥ 0.0 | Needs work | Enforced by SLSQP bounds `[(0.0, 1.0)] * n`. |
| All numeric outputs are Python `float` | Needs work | Requires explicit `float()` wrapping — numpy leaks on `scipy` result arrays. |
| risk_tolerance=0.0 allows concentration | Needs work | Objective weight on variance → 0; optimizer free to concentrate. |
| risk_tolerance=1.0 → ~equal weights | Needs work | Objective weight on return → 0; optimizer minimises variance only. |
| Empty tickers list → `_EMPTY_PORTFOLIO` | Needs work | Guard at function entry: `if not tickers: return _EMPTY_PORTFOLIO.copy()`. |
| Single ticker → `{"AAPL": 1.0}` weight | Needs work | Shortcut branch before calling optimizer. |
| Failed tickers silently dropped | Needs work | Filter out tickers where `get_stock_history` returns `[]` before building price matrix. |
| `risk_tolerance` outside [0,1] clamped | Needs work | `risk_tolerance = max(0.0, min(1.0, float(risk_tolerance)))` at entry. |
| `horizon_years` ≤ 0 → `_EMPTY_PORTFOLIO` | Needs work | Guard: `if not isinstance(horizon_years, (int, float)) or horizon_years <= 0`. |
| Fewer than 2 observations → `_EMPTY_PORTFOLIO` | Needs work | Check after `_build_price_matrix` returns. |
| `weights` is `dict[str, float]` (not list, not numpy) | Needs work | Build with `dict(zip(tickers, [float(w) for w in result.x]))`. |

---

## Dependencies

- `data/stock.py` — `get_stock_history` is the only inter-module dependency. Must be imported as `from data.stock import get_stock_history` and patched at `data.portfolio.get_stock_history` in tests.
- `scipy` — new external dependency, not yet in `requirements.txt`.
- `numpy` — already installed; used for log-return and covariance computation.
- No other modules are affected by this addition.
