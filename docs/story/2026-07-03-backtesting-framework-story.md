# User Story: Backtesting Framework
Date: 2026-07-03
Source: Pasted text — Story 18: Backtesting Framework

---

## Story 18: Backtest Trading Signals on Historical Stock Data

**As a** quantitative analyst using the AI Stock Intelligence Platform,
**I want** to replay BUY/HOLD/SELL signals against historical OHLCV data with realistic transaction costs and slippage,
**So that** I can measure the strategy's historical performance before deploying it with real capital.

### Scope In
- Single function `run_backtest(signals, ticker, start, end, initial_capital, transaction_cost_pct, slippage_pct)` in `data/backtester.py`
- Inputs: `signals` is a `list[dict]` with `{date: str, action: str}` entries matching the format already produced by `generate_recommendation`; `ticker`, `start`, `end` match `get_stock_history` conventions
- Buy/Sell execution model: apply slippage to fill price, deduct transaction cost from cash on each trade
- Long-only strategy: BUY opens a position (100% of available cash), SELL closes any open position, HOLD does nothing
- Portfolio tracking: one portfolio value data point per trading day in the signal window
- Performance metrics returned: `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return`
- Trade log returned: `trades` — list of closed round-trips with entry/exit date, price, and PnL
- `get_stock_history` used internally to fetch price data; consistent with the rest of the pipeline
- All-None / empty fallback dict on any failure; function never raises
- Pure Python + numpy only — no new heavy dependencies

### Scope Out
- Short-selling (no short positions in this iteration)
- Fractional shares (always whole-share lots)
- Intraday data or sub-daily resolution
- Live/paper-trading execution
- Portfolio-level multi-ticker backtesting (single ticker per call)
- Position sizing beyond 100%-of-cash on BUY
- Benchmark comparison (e.g. buy-and-hold vs strategy) — future story
- Visualisation / chart output

### Acceptance Criteria

- **Given** a valid ticker, date range, and a signals list containing at least one BUY followed by one SELL,
  **when** `run_backtest` is called with default cost parameters,
  **then** it returns a dict with keys `cagr`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_return`, `trades`, `portfolio_values`, all populated with Python-native types (float/list/dict, no numpy scalars).

- **Given** a BUY signal followed by a SELL signal,
  **when** the function executes the trade,
  **then** the buy fill price = close × (1 + slippage_pct), the sell fill price = close × (1 − slippage_pct), and the transaction cost (close × shares × transaction_cost_pct) is deducted from cash on each leg; the closed trade appears in `trades` with correct `pnl`.

- **Given** a portfolio that grows from initial capital to a final value,
  **when** `cagr` is computed,
  **then** it equals `(final_value / initial_capital) ** (1 / years) − 1` where `years` is the elapsed calendar days divided by 365.25.

- **Given** daily portfolio returns,
  **when** `sharpe_ratio` is computed,
  **then** it equals `mean(daily_returns) / std(daily_returns) × √252`; if std is zero, `sharpe_ratio` is `0.0`.

- **Given** the time series of portfolio values,
  **when** `max_drawdown` is computed,
  **then** it equals the largest peak-to-trough decline expressed as a negative float (e.g. `−0.15` for a 15% drawdown); `0.0` if no drawdown occurred.

- **Given** a completed list of round-trip trades,
  **when** `win_rate` is computed,
  **then** it equals the fraction of trades where `pnl > 0`; `0.0` if there are no closed trades.

- **Given** a signals list that contains only HOLD signals (no open position ever),
  **when** `run_backtest` is called,
  **then** `trades` is `[]`, `win_rate` is `0.0`, `total_return` is `0.0`, and `portfolio_values` tracks the unchanged initial capital across all dates.

- **Given** an invalid ticker, an empty signals list, or a date range that returns no price data,
  **when** `run_backtest` is called,
  **then** it returns `_EMPTY_RESULT.copy()` with all metric fields as `None` and `trades`/`portfolio_values` as `[]`; it never raises.

### Definition of Done
- [ ] `data/backtester.py` implemented with `run_backtest` matching the above contract
- [ ] `_EMPTY_RESULT` module-level constant; always `.copy()` on return
- [ ] All numeric outputs wrapped with `float()` — no numpy scalar leakage
- [ ] `tests/test_backtester.py` written (mock `get_stock_history`; no real HTTP calls)
- [ ] All tests passing with `& "Z:\python39\python.exe" -m pytest tests/test_backtester.py -v`
- [ ] Full suite still green: `& "Z:\python39\python.exe" -m pytest tests/ -v`
- [ ] `/test-review` run; Recommendation: Ready (no Meaningless, <25% Weak)

---
