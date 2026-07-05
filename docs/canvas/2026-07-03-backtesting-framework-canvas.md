# REASONS Canvas: Backtesting Framework
Date: 2026-07-03
Analysis: 2026-07-03-backtesting-framework-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The pipeline can generate BUY/HOLD/SELL signals but has no way to measure how well those signals would have performed on real historical price data. There is no mechanism to quantify strategy quality before deployment.

**Goal:** Add a `run_backtest` function in a new `data/backtester.py` module that replays a list of trading signals against historical close prices, applies slippage and transaction costs, and returns five performance metrics plus a full trade log and daily portfolio value series.

**Definition of Done:**
- [ ] Given a valid ticker, date range, and signals list with at least one BUY followed by a SELL, when `run_backtest` is called, then it returns a dict with exactly the keys `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return`, `trades`, and `portfolio_values`, all as Python-native types with no numpy scalars
- [ ] Given a BUY signal on date D, when executed, then the fill price equals the close price on D multiplied by one plus slippage_pct, the number of shares equals the integer floor of available cash divided by fill price, and the transaction cost equals fill price times shares times transaction_cost_pct deducted from cash; the mirror logic applies to the SELL leg with fill price reduced by slippage_pct
- [ ] Given an elapsed calendar day count of N between the first and last price dates, when CAGR is computed, then the result equals final portfolio value divided by initial capital raised to the power of 365.25 divided by N, minus one; if N is zero or less then CAGR is zero
- [ ] Given the daily portfolio value series, when Sharpe is computed, then it equals the mean of daily percentage returns divided by their standard deviation multiplied by the square root of 252; if standard deviation is zero then Sharpe is zero
- [ ] Given the daily portfolio value series, when max drawdown is computed, then it equals the most-negative peak-to-trough percentage decline as a negative float; if no drawdown occurs then it is zero
- [ ] Given the completed list of round-trip trades, when win rate is computed, then it equals the count of trades where PnL is greater than zero divided by the total number of trades; if trades is empty then win rate is zero
- [ ] Given a signals list containing only HOLD signals, when `run_backtest` is called, then trades is an empty list, win_rate is zero, total_return is zero, and portfolio_values tracks the unchanged initial capital for every date
- [ ] Given an invalid ticker, empty signals list, negative initial_capital, negative cost parameters, or a date range that returns no price data, when `run_backtest` is called, then it returns `_EMPTY_RESULT.copy()` with all metric fields as None and trades and portfolio_values as empty lists; it never raises an exception

---

## E — Entities

### Data Contracts

| Name | Kind | Shape | Notes |
|------|------|-------|-------|
| `signals` input | list of dicts | each dict has a `date` key (YYYY-MM-DD string) and an `action` key (any case: Buy/BUY/buy) | Normalised to uppercase inside the simulation; dates not found in the price map are silently skipped |
| `_EMPTY_RESULT` | module constant | seven keys: `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return` all None; `trades` and `portfolio_values` as empty lists | Always returned via `.copy()`; never mutated |
| price map | internal dict | maps date string to float close price; built from `get_stock_history` output | Keyed by the same YYYY-MM-DD strings as the signals input |
| trade record | dict per closed round-trip | keys: `entry_date`, `exit_date`, `entry_price`, `exit_price`, `shares`, `pnl` — all Python-native types | Appended on every SELL or forced end-of-window liquidation |
| portfolio value entry | dict per trading day | keys: `date` (string), `value` (float) | One entry per date in the price map; value is shares times current close when in position, otherwise remaining cash |
| `run_backtest` return dict | public return value | seven keys: `cagr (float)`, `sharpe_ratio (float)`, `max_drawdown (float)`, `win_rate (float)`, `total_return (float)`, `trades (list)`, `portfolio_values (list)` | All floats wrapped with `float()`; no numpy scalar leakage |

### Dependencies on Existing Modules

| Module | Function Used | How Used |
|--------|--------------|----------|
| `data/stock.py` | `get_stock_history(ticker, start, end)` | Called once inside `run_backtest` to fetch the price series; mocked in all tests |
| `numpy` | `np.array`, `np.std`, `np.mean`, `np.diff` | Used only inside metric helpers, not in the simulation loop |
| `math` | `math.sqrt`, `math.isfinite` | Used in Sharpe (sqrt 252) and input validation |

---

## A — Approach

**Pattern:** Pure Python simulation module — thin public orchestrator delegating to private helpers.

**Strategy:** Model the module after `data/risk.py`: `run_backtest` validates inputs and then calls `_build_price_map`, `_execute_simulation`, and the four metric helpers in sequence. The simulation loop itself is plain Python (no numpy), iterating over sorted price dates and executing signal logic with simple arithmetic. numpy is confined to the four metric helpers where vectorised operations genuinely help. Each helper is independently testable. The only external call is `get_stock_history`, which is mocked in tests.

**Scope In:**
- Single-ticker, long-only backtesting with whole-share lots
- Slippage on fill price and transaction cost deducted from cash on each trade leg
- Five return metrics: CAGR, Sharpe Ratio, Maximum Drawdown, Win Rate, Total Return
- Daily portfolio value series covering every date in the price map
- Trade log of closed round-trips; open position at window end force-liquidated at last close
- Pre-flight validation of initial_capital, transaction_cost_pct, and slippage_pct

**Scope Out:**
- Short-selling or margin trading
- Fractional shares
- Multi-ticker or portfolio-level backtesting
- Benchmark comparison (buy-and-hold versus strategy)
- Intraday resolution or sub-daily signals
- Visualisation or chart output
- Position sizing other than 100-percent-of-cash on BUY

---

## S — Structure

**Module path:** `Z:\claude\stock_analyzer\data\backtester.py`

**New Files:**
- `data/backtester.py` — entire new module: `_EMPTY_RESULT` constant, six private helpers, one public function
- `tests/test_backtester.py` — full test suite; mocks `data.backtester.get_stock_history`

**Modified Files:**
- None — no existing module needs to change

**New Dependencies:**
- None — numpy and math are already installed and imported by other modules

---

## O — Operations

1. Create `data/backtester.py` with module-level imports (`math`, `numpy`, and `from data.stock import get_stock_history`), define `_EMPTY_RESULT` as a dict with `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return` all set to None and `trades` and `portfolio_values` set to empty lists; also define the `_safe_float` private helper that returns None for None or non-numeric input and a Python float otherwise

2. Implement `_build_price_map(history)` — accepts a list of OHLCV dicts as returned by `get_stock_history`; iterates over the list and builds a dict mapping each date string to the float close price; returns an empty dict if history is empty or None

3. Implement `_compute_cagr(initial_capital, final_value, n_calendar_days)` — computes compound annual growth rate as final divided by initial raised to the power of 365.25 divided by n_calendar_days then minus one; returns zero if n_calendar_days is zero or less, or if initial_capital is zero; wraps result in `float()`

4. Implement `_compute_sharpe(portfolio_values)` — accepts the portfolio_values list of dicts; extracts the `value` field from each entry in date order to form a numpy array; computes daily percentage returns as the difference of consecutive values divided by the prior value; returns mean of returns divided by standard deviation multiplied by sqrt of 252 as a Python float; returns zero if fewer than two values or if standard deviation is zero

5. Implement `_compute_max_drawdown(portfolio_values)` — extracts the `value` series; iterates tracking a running peak and computes the drawdown at each point as current value minus peak divided by peak; returns the minimum drawdown as a negative float wrapped in `float()`; returns zero if no drawdown occurred or fewer than two values

6. Implement `_compute_win_rate(trades)` — counts the number of trade dicts where `pnl` is greater than zero and divides by the total number of trades; returns zero if trades is an empty list; wraps result in `float()`

7. Implement `_execute_simulation(price_map, signals, initial_capital, transaction_cost_pct, slippage_pct)` — builds a date-to-action lookup from signals by normalising each action string to uppercase; iterates over all dates in the price map in ascending sorted order; on each date checks if a signal exists and executes it: for BUY when flat compute fill price as close times one plus slippage_pct, compute shares as integer floor of cash divided by fill price, skip if shares is zero, deduct fill price times shares times transaction_cost_pct from cash and record entry state; for SELL when in position compute fill price as close times one minus slippage_pct, compute proceeds as fill price times shares minus fill price times shares times transaction_cost_pct, add proceeds to cash, append a trade record dict with entry_date, exit_date, entry_price, exit_price, shares, and pnl as Python floats, and clear position state; on every date append a portfolio_values entry with the date and the current value as shares times close if in position else cash; after the loop if still in position force-liquidate at the last close price and append a final trade record; returns a tuple of (trades list, portfolio_values list, final cash float)

8. Implement `run_backtest(signals, ticker, start, end, initial_capital=10000.0, transaction_cost_pct=0.001, slippage_pct=0.001)` — validate that signals is a list, that initial_capital is positive and finite, and that transaction_cost_pct and slippage_pct are both non-negative and finite; return `_EMPTY_RESULT.copy()` on any invalid input; call `get_stock_history(ticker, start, end)`; return `_EMPTY_RESULT.copy()` if result is empty; build the price map via `_build_price_map`; call `_execute_simulation` to get trades, portfolio_values, and final_value; compute n_calendar_days from the date strings of the first and last price entries; compute total_return as final_value minus initial_capital divided by initial_capital; assemble and return a dict with cagr from `_compute_cagr`, sharpe_ratio from `_compute_sharpe`, max_drawdown from `_compute_max_drawdown`, win_rate from `_compute_win_rate`, total_return, trades, and portfolio_values; wrap the entire function body in a try-except Exception that returns `_EMPTY_RESULT.copy()` on any unhandled error; never raise

9. Create `tests/test_backtester.py` — patch `data.backtester.get_stock_history` in all tests; build a reusable mock price series helper that returns a list of OHLCV dicts for a given date range with configurable close prices; cover the following test classes: OutputSchema (return dict has exactly seven keys; all metric fields are Python float not numpy; trades is a list of dicts; portfolio_values is a list of dicts with date and value keys), TradeExecution (buy fill price includes slippage; sell fill price reduces by slippage; transaction cost deducted on each leg; PnL in trade record is correct; shares is integer floor; BUY when already in position is a no-op; SELL when flat is a no-op), MetricComputation (CAGR matches formula for known initial and final values; Sharpe is zero when all returns are identical; max drawdown is the correct negative value for a known series; max drawdown is zero when portfolio only grows; win rate is correct fraction; win rate is zero for empty trades list), EdgeCases (HOLD-only signals produce empty trades and zero total_return; signal date not in price map is silently skipped; open position at window end is force-liquidated and appears in trades; BUY with zero purchasable shares is a no-op), PreflightGuards (empty signals list returns all-None result; negative initial_capital returns all-None result; negative transaction_cost_pct returns all-None result; negative slippage_pct returns all-None result; get_stock_history returning empty list returns all-None result; exception inside get_stock_history returns all-None result)

---

## N — Norms

### Python Pipeline Norms

- Every public function has a single outer `try/except Exception` boundary — it never raises to the caller
- Return dicts use Python-native types only — no numpy scalars, no pandas objects; wrap all computed floats with `float()`
- Module-level constants for fallback dicts (named `_EMPTY_RESULT`); always return `.copy()` — never return the constant itself
- Private helpers are prefixed with underscore; the public function is a thin orchestrator that validates then delegates
- Copy private helpers like `_safe_float` locally — do not import private symbols from other modules
- No external HTTP calls inside the module beyond the single call to `get_stock_history`; all tests mock this call
- No pandas dependency — use plain Python dicts and lists for simulation; numpy only for metric computation
- Python 3.9 compatibility — no bare `X | Y` union type hints in signatures; use string annotations if needed

---

## S — Safeguards

### General Pipeline Safeguards

- Never raise an exception to the caller — all error paths return `_EMPTY_RESULT.copy()`
- Never mutate `_EMPTY_RESULT` directly — always return `.copy()`
- Never return a numpy scalar from a public function — wrap every metric value with `float()`
- Do not import private helpers from other `data/` modules — copy them locally
- All tests must mock `data.backtester.get_stock_history`; no test may make a real HTTP call

### Feature-Specific Safeguards

- Signals whose date string is absent from the price map must be silently skipped — they are not errors
- A BUY signal when already in position is a no-op — do not double-buy; do not raise
- A SELL signal when flat is a no-op — do not raise
- If `int(cash / fill_price)` is zero on a BUY, skip the trade — opening a zero-share position would cause downstream division errors
- Negative `transaction_cost_pct` or `slippage_pct` are rejected in pre-flight — they would produce non-physical inflated returns
- `_compute_sharpe` must guard `std == 0` explicitly and return `0.0` — an all-HOLD run produces a flat portfolio_values series with zero variance
- An open position remaining at the end of the date window must be force-liquidated at the last available close price and recorded as a closed trade — leaving a phantom open position would make the final portfolio value and trade log inconsistent

---

## Change Log

- 2026-07-03: Initial canvas generated from analysis `2026-07-03-backtesting-framework-analysis.md`
