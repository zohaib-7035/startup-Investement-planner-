# Analysis: Backtesting Framework
Date: 2026-07-03
Story: 2026-07-03-backtesting-framework-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline with no web framework or ORM. Module-per-concern layout under `data/`; every public function has a full exception boundary and returns Python-native types only. numpy 1.26.4 and scipy are already installed. No new packages are needed for this story.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `get_stock_history(ticker, start, end)` | `data/stock.py:7` | Returns sorted `list[dict]` with `{date, open, high, low, close, volume}`; returns `[]` on any failure |
| `generate_recommendation(rsi, eps_surprise, pe_ratio)` | `data/screener.py:24` | Returns `{action, confidence, reason}`; action is title-case `"Buy"/"Sell"/"Hold"` |
| `aggregate_signals` action strings | `data/meta_agent.py:10` | Uses all-caps `"BUY"/"SELL"/"HOLD"` — different case convention from screener |
| `_EMPTY_RESULT` pattern | `data/risk.py:5`, `data/meta_agent.py:1`, `data/notifier.py` | Module-level fallback constant; always returned via `.copy()` |
| `_safe_float` helper | `data/stock.py:66`, `data/portfolio.py:17` | Each module copies the helper — no cross-module import |
| `_build_portfolio_series` | `data/risk.py:22` | Builds weighted log-return array from `get_stock_history`-shaped input — similar date-alignment pattern needed in backtester |
| numpy log/percentile/std operations | `data/risk.py`, `data/portfolio.py` | Established patterns for annualised vol, percentile-based risk — Sharpe and max-drawdown follow same idioms |

### Missing / Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/backtester.py` | New module | Entire module is new |
| `run_backtest(signals, ticker, start, end, initial_capital, transaction_cost_pct, slippage_pct)` | Public function | Main entry point; must match universal pipeline rules |
| `_EMPTY_RESULT` | Module-level constant | 7 keys: `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return` all `None`; `trades` and `portfolio_values` as `[]` |
| `_build_price_map(history)` | Private helper | Converts `get_stock_history` output to `{date_str: close_float}` dict for O(1) signal-date lookup |
| `_execute_simulation(price_map, signals, initial_capital, transaction_cost_pct, slippage_pct)` | Private helper | Core simulation loop; returns `(trades, portfolio_values, cash)` |
| `_compute_cagr(initial_capital, final_value, n_calendar_days)` | Private helper | `(final/initial) ** (365.25 / days) - 1`; returns `0.0` if days ≤ 0 |
| `_compute_sharpe(portfolio_values)` | Private helper | Daily pct-change series → `mean/std × √252`; returns `0.0` if std is zero or fewer than 2 values |
| `_compute_max_drawdown(portfolio_values)` | Private helper | Running-peak method; returns most-negative float, `0.0` if no drawdown |
| `_compute_win_rate(trades)` | Private helper | `count(pnl > 0) / len(trades)`; returns `0.0` if trades is empty |
| `tests/test_backtester.py` | Test file | Mocks `get_stock_history`; no real HTTP calls |

---

## Strategic Approach

Build `data/backtester.py` as a pure simulation module following the same structure as `data/risk.py`: a thin public function that validates inputs and delegates to private helpers, with numpy used only for metric computation (not the simulation loop itself). The simulation loop iterates over price dates in order, executing signals when a matching date is found and tracking portfolio value daily — this avoids any dependency on pandas and keeps the module pure-Python + numpy. All metric helpers are independent and unit-testable in isolation. The `get_stock_history` call is the only external dependency, so mocking it is sufficient to test all paths.

---

## Key Design Decisions

- **Case normalisation on input:** `generate_recommendation` returns title-case (`"Buy"`) while `meta_agent` uses uppercase (`"BUY"`). Normalise action strings to uppercase inside `_execute_simulation` so both formats work without the caller needing to pre-process signals.
- **Signal-date alignment:** Signals carry a date string; prices only exist for trading days. If a signal date has no matching price (weekend, holiday), it is silently skipped — consistent with how `risk.py` inner-joins on common dates.
- **Position guard:** A BUY signal when already in position is a no-op (no double-buying). A SELL signal with no open position is a no-op. These are expected real-world cases, not errors.
- **Whole-share lots:** `shares = int(cash / fill_price)` using `int()` truncation — matches the scope-out of fractional shares.
- **Fill price model:** BUY fill = `close × (1 + slippage_pct)`; SELL fill = `close × (1 - slippage_pct)`. Transaction cost deducted separately as `fill_price × shares × transaction_cost_pct` from cash on each leg.
- **Portfolio value per day:** Computed for every date in the price map (not just signal dates). In-position: `shares × close`. Flat: remaining cash. This ensures `portfolio_values` has a data point for every trading day and Sharpe/drawdown have the full return series.
- **No cross-module `_safe_float` import:** Copy the helper locally — matches the established pattern in `stock.py` and `portfolio.py`.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Signal date not in price map (weekend / holiday) | Medium | Silently skip the signal — same inner-join semantics as `risk.py`. Test this case explicitly. |
| BUY with zero shares purchasable (cash < fill_price) | Medium | `int(cash / fill_price) == 0` → treat as no-op, do not open position. Otherwise division errors downstream. |
| All-HOLD or empty signals list — std of returns is zero | Low | `_compute_sharpe` must guard `std == 0` → return `0.0`. Already handled in `portfolio.py` Sharpe pattern. |
| `initial_capital` ≤ 0 or non-numeric | Low | Validate in `run_backtest` pre-flight; return `_EMPTY_RESULT.copy()` immediately. |
| `transaction_cost_pct` or `slippage_pct` < 0 | Low | Validate; negative costs would inflate returns non-physically. |
| numpy scalar leakage in returned metrics | High | All five metric floats must be wrapped with `float()`. Same risk burned `portfolio.py` in test-review — pre-empt it. |
| Fewer than 2 portfolio value entries | Low | Need at least 2 for daily returns. Guard in `_compute_sharpe` and `_compute_max_drawdown`. |
| Open position at end of backtest window (no SELL before end) | Medium | Position is liquidated at last available close price. Record the forced-close as a closed trade. |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns 7-key dict with Python-native types | Needs work | `backtester.py` does not exist yet; `float()` wrapping required |
| BUY/SELL fill prices include slippage; cost deducted from cash | Needs work | Implemented in `_execute_simulation`; straightforward arithmetic |
| CAGR formula: `(final/initial)^(1/years) - 1` | Needs work | `_compute_cagr`; use calendar days ÷ 365.25 for `years` |
| Sharpe = `mean/std × √252`; 0.0 if std is zero | Needs work | `_compute_sharpe`; guard already established in `portfolio.py` |
| Max drawdown = most-negative peak-to-trough float | Needs work | `_compute_max_drawdown`; running-peak method; `0.0` if no drawdown |
| Win rate = fraction of trades with PnL > 0; 0.0 if no trades | Needs work | `_compute_win_rate`; empty-list guard required |
| HOLD-only signals → empty trades, zero return, constant portfolio | Needs work | No-op simulation; `total_return = 0.0`, `portfolio_values` tracks initial capital |
| Invalid input returns `_EMPTY_RESULT.copy()`; never raises | Needs work | Outer `try/except Exception` + pre-flight guards on `initial_capital`, cost params |

---

## Dependencies

- `data/stock.py → get_stock_history` — only external call; mocked in all tests
- `numpy` (1.26.4, already installed) — for `np.std`, `np.mean`, `math.sqrt(252)`
- No other modules are affected by adding `data/backtester.py`
