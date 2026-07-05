# Analysis: Risk Calculation Agent

Date: 2026-07-03
Story: docs/story/2026-07-03-risk-calculation-agent-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline with 13 modules under `data/`, each owning one concern and exposing one or two public functions. No web framework, no ORM, no persistence layer. Core numeric stack: numpy==1.26.4, scipy>=1.11, pandas==2.2.2. LLM calls use anthropic==0.40.0. External data via yfinance, openbb==4.3.2, requests. Vector storage via chromadb + sentence-transformers. All modules follow the pattern: module-level fallback constant → try/except boundary → _safe_* helpers → Python-native return types.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_EMPTY_PORTFOLIO` constant | `data/portfolio.py:9` | Module-level all-None fallback; `.copy()` on return — exact pattern to replicate |
| `_build_price_matrix(tickers, start, end)` | `data/portfolio.py:26` | Inner-joins dates across tickers, returns (np.ndarray, surviving_tickers) — the date-alignment logic risk.py needs already exists here as a model |
| `_compute_stats(weights_array, mean_returns, cov_matrix)` | `data/portfolio.py:65` | Annualised return, vol, Sharpe using float(np.dot(...)) — demonstrates the float() wrap to prevent numpy scalar leakage |
| `_CONFIDENCE_MAP` + rule-ordered if/elif/else | `data/screener.py:3` | Classification-table pattern; risk_level map should follow the same constant-lookup idiom |
| Outer `try/except Exception → _EMPTY_RESULT.copy()` | `data/graph_reasoning.py:98` | Universal error boundary; also demonstrates that _EMPTY_RESULT can be a plain dict constant when no caller-supplied name is needed |
| `_safe_rsi` / `_safe_float` helpers | `data/screener.py:12`, `data/portfolio.py:17` | Input validation pattern: float() cast → math.isfinite guard → None on failure |
| numpy log-return computation | `data/portfolio.py:107` | `np.log(prices[1:] / prices[:-1])` — available and tested |
| `numpy.percentile` | numpy==1.26.4 | Used in VaR calculation — no new import needed |
| `math.sqrt` | stdlib | Already used in `_compute_stats` for port_vol — use same pattern for ×√horizon_days scaling |
| `_make_history(prices)` test fixture | `tests/test_portfolio.py:7` | Builds get_stock_history-shaped list[dict]; test_risk.py will use the same shape |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/risk.py` | New Python module | Does not exist; will hold all risk calculation logic |
| `calculate_risk_metrics(weights, returns_data, confidence_level=0.95, horizon_days=5)` | Public function | Entry point; `returns_data` format: `dict[str, list[dict]]` — same shape as `get_stock_history()` output |
| `_EMPTY_RESULT` | Module-level dict constant | 6-key all-None fallback: `{var_1w_95: None, cvar_1w_95: None, portfolio_volatility: None, concentration_risk: None, risk_level: None, warnings: None}` |
| `_build_portfolio_series(weights, returns_data)` | Private helper | Inner-joins dates, extracts close prices, computes log returns, applies normalised weights → weighted daily return series as np.ndarray. Returns None if fewer than 2 aligned rows |
| `_compute_var_cvar(portfolio_series, confidence_level, horizon_days)` | Private helper | daily_var = abs(np.percentile(series, (1-cl)*100)); cvar = abs(mean of series ≤ -daily_var); both scaled by math.sqrt(horizon_days) |
| `_compute_concentration(weights)` | Private helper | sum(w**2 for w in weights.values()) — HHI; single-ticker → 1.0 |
| `_classify_risk_level(var_1w, concentration)` | Private helper | Ordered threshold table → "Low"/"Medium"/"High"/"Critical" |
| `_build_warnings(var_1w, concentration, n_tickers)` | Private helper | Returns list[str]; checks single asset, concentration > 0.40, VaR > 0.05 |
| `_RISK_THRESHOLDS` | Module-level constant | Ordered list of (var_threshold, conc_threshold, label) tuples for classification |
| `tests/test_risk.py` | New test file | No mocking needed (pure computation); uses inline returns_data fixture; follows screener.py direct-call pattern |

---

## Strategic Approach

`data/risk.py` is a pure-Python/numpy computation module — the closest relatives are `data/screener.py` (rule table + classification) and `data/portfolio.py` (numpy array ops + annualised stats). The function accepts pre-fetched price data in `get_stock_history()` dict-list format so it has no external calls and needs no mocking in tests. The computation pipeline is: inner-join dates → log return matrix → weighted portfolio series → percentile VaR → CVaR tail mean → annualised volatility → HHI concentration → threshold classification → warnings list. All intermediate numpy outputs are wrapped with `float()` before being written into the return dict, following the anti-leakage pattern already established in `_compute_stats` in `portfolio.py`.

---

## Key Design Decisions

- `returns_data` shape is `dict[str, list[dict]]` — same as `get_stock_history()` output — so callers compose the pipeline naturally without a data-transformation step between fetching and risk calculation.
- No internal calls to `get_stock_history()` — unlike `portfolio.py`, risk.py receives pre-fetched data. This keeps the function pure and testable without mocking.
- Log returns (not simple returns) — consistent with `portfolio.py:107`; log returns are additive and numerically stable for multi-day scaling.
- VaR scaled by √horizon_days — the square-root-of-time rule; daily VaR = abs(np.percentile(series, (1-c)*100)); 1-week VaR = daily VaR × √5.
- CVaR = mean of tail returns ≤ −daily_var — Expected Shortfall; also scaled by √5 before return.
- Tickers in weights absent from returns_data are dropped by the inner-join; surviving weights are re-normalised (sum to 1.0) before the weighted sum to ensure a properly scaled portfolio series.
- `_EMPTY_RESULT` is a dict constant, not a factory — no caller-supplied values belong in the risk fallback (unlike graph_reasoning where entity name was needed).
- Classification uses ordered thresholds: Critical if VaR ≥ 0.10 or concentration ≥ 0.60; High if VaR ≥ 0.05 or concentration ≥ 0.40; Medium if VaR ≥ 0.02 or concentration ≥ 0.25; Low otherwise.
- `confidence_level` outside (0,1) and `horizon_days ≤ 0` both return `_EMPTY_RESULT.copy()` after validation.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Tickers in weights absent from returns_data — surviving weight vector no longer sums to 1.0 | High | Normalise surviving weights before weighted-sum step |
| Fewer than 2 aligned date rows after inner-join | High | `_build_portfolio_series` returns None → outer guard returns `_EMPTY_RESULT.copy()` |
| All tickers in weights absent from returns_data | High | Same guard — None from helper → `_EMPTY_RESULT.copy()` |
| numpy scalar leakage in return dict | Medium | All numeric outputs must be wrapped with float() — verified by `assertIs(type(...), float)` tests |
| Perfectly flat time series (zero variance) → VaR = 0.0, CVaR = 0.0 | Medium | Valid output — no division by zero in this path; test must confirm 0.0 returned without error |
| CVaR with no tail observations (all returns above VaR threshold) | Medium | Guard: if tail is empty, return VaR itself as CVaR (CVaR ≥ VaR by definition) |
| `confidence_level` very close to 1.0 with small sample → empty tail | Low | Same empty-tail guard covers this |
| `horizon_days ≤ 0` or non-numeric | Low | Validate before computation; return `_EMPTY_RESULT.copy()` |
| Python 3.9 bare `X | Y` union type hints | Low | Use string annotations: `"float | None"` in all private helper signatures |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns 6-key dict with all fields present and not None on valid input | Needs work | data/risk.py does not exist; numpy infrastructure already installed |
| Inner-join on dates → weighted return series → VaR = abs(percentile) × √5 | Needs work | _build_price_matrix in portfolio.py is the exact model for the date-alignment step |
| CVaR = mean of tail losses × √5 | Needs work | numpy mean on a boolean-masked array; no new dependency |
| Concentration (HHI) > 0.40 triggers "concentration" warning | Needs work | Threshold logic and warnings builder are new; _CONFIDENCE_MAP is the pattern model |
| VaR > 0.05 → risk_level "High" or "Critical" + "VaR" warning | Needs work | Classification table and warning builder are new |
| Invalid/missing inputs → _EMPTY_RESULT.copy(), no exception | Needs work | Outer try/except pattern already established in all 13 existing modules |
| Single-ticker → concentration_risk == 1.0, "single asset" warning, all float | Needs work | HHI of {w: 1.0} = 1.0 naturally; n_tickers==1 check triggers warning |

---

## Dependencies

- `data/stock.py` (get_stock_history) — called by the caller to produce returns_data; NOT called inside data/risk.py
- numpy — log returns, percentile, mean, array ops (already in requirements.txt)
- math — sqrt, isfinite (stdlib; already used by portfolio.py and screener.py)
- No new packages required; requirements.txt unchanged
