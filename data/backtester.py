import math
from datetime import datetime

import numpy as np

from data.stock import get_stock_history

_EMPTY_RESULT = {
    "cagr": None,
    "sharpe_ratio": None,
    "max_drawdown": None,
    "win_rate": None,
    "total_return": None,
    "trades": [],
    "portfolio_values": [],
}


def _safe_float(value) -> "float | None":
    if value is None or isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Operation 2: price map builder
def _build_price_map(history) -> dict:
    if not history:
        return {}
    result = {}
    for row in history:
        date = row.get("date")
        close = row.get("close")
        if date is not None and close is not None:
            result[date] = float(close)
    return result


# Operation 3: CAGR
def _compute_cagr(initial_capital: float, final_value: float, n_calendar_days: int) -> float:
    if n_calendar_days <= 0 or initial_capital == 0:
        return 0.0
    years = n_calendar_days / 365.25
    return float((final_value / initial_capital) ** (1.0 / years) - 1.0)


# Operation 4: Sharpe ratio
def _compute_sharpe(portfolio_values: list) -> float:
    if len(portfolio_values) < 2:
        return 0.0
    values = np.array([e["value"] for e in portfolio_values], dtype=float)
    daily_returns = np.diff(values) / values[:-1]
    if len(daily_returns) < 2:
        return 0.0
    std = float(np.std(daily_returns, ddof=1))
    if std == 0.0:
        return 0.0
    return float(float(np.mean(daily_returns)) / std * math.sqrt(252))


# Operation 5: maximum drawdown
def _compute_max_drawdown(portfolio_values: list) -> float:
    if len(portfolio_values) < 2:
        return 0.0
    peak = portfolio_values[0]["value"]
    max_dd = 0.0
    for entry in portfolio_values:
        v = entry["value"]
        if v > peak:
            peak = v
        if peak > 0.0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return float(max_dd)


# Operation 6: win rate
def _compute_win_rate(trades: list) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    return float(wins / len(trades))


# Operation 7: core simulation loop
def _execute_simulation(price_map, signals, initial_capital, transaction_cost_pct, slippage_pct):
    signal_map = {}
    for sig in signals:
        date = sig.get("date")
        action = sig.get("action")
        if date is not None and action is not None:
            signal_map[date] = str(action).upper()

    cash = float(initial_capital)
    shares = 0
    entry_date = None
    entry_price = None
    entry_total_cost = 0.0
    trades = []
    portfolio_values = []
    sorted_dates = sorted(price_map.keys())

    for date in sorted_dates:
        close = price_map[date]
        action = signal_map.get(date)

        if action == "BUY" and shares == 0:
            fill_price = close * (1.0 + slippage_pct)
            n_shares = int(cash / fill_price)
            if n_shares > 0:
                buy_tc = fill_price * n_shares * transaction_cost_pct
                cash_out = fill_price * n_shares + buy_tc
                cash -= cash_out
                shares = n_shares
                entry_date = date
                entry_price = fill_price
                entry_total_cost = cash_out

        elif action == "SELL" and shares > 0:
            fill_price = close * (1.0 - slippage_pct)
            gross = fill_price * shares
            sell_tc = fill_price * shares * transaction_cost_pct
            net_proceeds = gross - sell_tc
            pnl = net_proceeds - entry_total_cost
            cash += net_proceeds
            trades.append({
                "entry_date": entry_date,
                "exit_date": date,
                "entry_price": float(entry_price),
                "exit_price": float(fill_price),
                "shares": shares,
                "pnl": float(pnl),
            })
            shares = 0
            entry_date = None
            entry_price = None
            entry_total_cost = 0.0

        portfolio_values.append({
            "date": date,
            "value": float(shares * close + cash) if shares > 0 else float(cash),
        })

    # Force-liquidate any open position at the last available close
    if shares > 0 and sorted_dates:
        last_date = sorted_dates[-1]
        last_close = price_map[last_date]
        fill_price = last_close * (1.0 - slippage_pct)
        gross = fill_price * shares
        sell_tc = fill_price * shares * transaction_cost_pct
        net_proceeds = gross - sell_tc
        pnl = net_proceeds - entry_total_cost
        cash += net_proceeds
        trades.append({
            "entry_date": entry_date,
            "exit_date": last_date,
            "entry_price": float(entry_price),
            "exit_price": float(fill_price),
            "shares": shares,
            "pnl": float(pnl),
        })
        if portfolio_values:
            portfolio_values[-1]["value"] = float(cash)

    return trades, portfolio_values, float(cash)


# Operation 8: thin public orchestrator
def run_backtest(
    signals,
    ticker,
    start,
    end,
    initial_capital=10000.0,
    transaction_cost_pct=0.001,
    slippage_pct=0.001,
) -> dict:
    """
    Backtest trading signals against historical close prices.
    Returns {cagr, sharpe_ratio, max_drawdown, win_rate, total_return, trades, portfolio_values}.
    Never raises.
    """
    try:
        if not isinstance(signals, list) or not signals:
            return _EMPTY_RESULT.copy()

        try:
            ic = float(initial_capital)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if not math.isfinite(ic) or ic <= 0:
            return _EMPTY_RESULT.copy()

        try:
            tc = float(transaction_cost_pct)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if not math.isfinite(tc) or tc < 0:
            return _EMPTY_RESULT.copy()

        try:
            sp = float(slippage_pct)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if not math.isfinite(sp) or sp < 0:
            return _EMPTY_RESULT.copy()

        history = get_stock_history(ticker, start, end)
        if not history:
            return _EMPTY_RESULT.copy()

        price_map = _build_price_map(history)
        if not price_map:
            return _EMPTY_RESULT.copy()

        trades, portfolio_values, final_value = _execute_simulation(
            price_map, signals, ic, tc, sp
        )

        sorted_dates = sorted(price_map.keys())
        first_dt = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
        last_dt = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")
        n_calendar_days = (last_dt - first_dt).days

        total_return = float((final_value - ic) / ic)

        return {
            "cagr": _compute_cagr(ic, final_value, n_calendar_days),
            "sharpe_ratio": _compute_sharpe(portfolio_values),
            "max_drawdown": _compute_max_drawdown(portfolio_values),
            "win_rate": _compute_win_rate(trades),
            "total_return": total_return,
            "trades": trades,
            "portfolio_values": portfolio_values,
        }

    except Exception:
        return _EMPTY_RESULT.copy()
