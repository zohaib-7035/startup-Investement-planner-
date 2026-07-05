import datetime
import math

import numpy as np
from scipy.optimize import minimize

from data.stock import get_stock_history

_EMPTY_PORTFOLIO = {
    "weights": None,
    "expected_return": None,
    "volatility": None,
    "sharpe_ratio": None,
}


def _safe_float(value) -> "float | None":
    if value is None or isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_price_matrix(tickers, start, end):
    """
    Fetch close prices for each ticker and inner-join on date.
    Returns (price_array, surviving_tickers) where price_array has shape
    (n_days, n_tickers). Returns (None, []) if fewer than 2 aligned rows.
    """
    date_to_prices = {}
    surviving = []

    for ticker in tickers:
        history = get_stock_history(ticker, start, end)
        if not history:
            continue
        surviving.append(ticker)
        for row in history:
            date = row["date"]
            if date not in date_to_prices:
                date_to_prices[date] = {}
            date_to_prices[date][ticker] = row["close"]

    if not surviving:
        return None, []

    common_dates = sorted(
        date
        for date, prices in date_to_prices.items()
        if len(prices) == len(surviving)
    )

    if len(common_dates) < 2:
        return None, []

    matrix = np.array(
        [[date_to_prices[d][t] for t in surviving] for d in common_dates],
        dtype=float,
    )
    return matrix, surviving


def _compute_stats(weights_array, mean_returns, cov_matrix):
    """
    Compute annualised portfolio return, volatility, and Sharpe ratio.
    All outputs are Python float.
    """
    port_return = float(np.dot(weights_array, mean_returns))
    port_variance = float(np.dot(weights_array, np.dot(cov_matrix, weights_array)))
    port_vol = float(math.sqrt(max(port_variance, 0.0)))
    sharpe = float(port_return / port_vol) if port_vol > 0.0 else 0.0
    return port_return, port_vol, sharpe


def optimize_portfolio(tickers, risk_tolerance, horizon_years) -> dict:
    """
    Markowitz mean-variance optimisation for a list of tickers.
    Returns {weights, expected_return, volatility, sharpe_ratio} — all
    Python-native floats. Never raises.
    """
    try:
        if not tickers:
            return _EMPTY_PORTFOLIO.copy()

        try:
            hy = float(horizon_years)
        except (TypeError, ValueError):
            return _EMPTY_PORTFOLIO.copy()
        if not math.isfinite(hy) or hy <= 0:
            return _EMPTY_PORTFOLIO.copy()

        try:
            rt = float(risk_tolerance)
        except (TypeError, ValueError):
            rt = 0.5
        rt = max(0.0, min(1.0, rt))

        end = datetime.date.today()
        start = end - datetime.timedelta(days=int(hy * 365))

        price_matrix, surviving = _build_price_matrix(tickers, start, end)
        if price_matrix is None or len(price_matrix) < 2:
            return _EMPTY_PORTFOLIO.copy()

        log_returns = np.log(price_matrix[1:] / price_matrix[:-1])
        mean_returns = log_returns.mean(axis=0) * 252
        cov_matrix = np.cov(log_returns, rowvar=False) * 252

        if len(surviving) == 1:
            ticker = surviving[0]
            port_return, port_vol, sharpe = _compute_stats(
                np.array([1.0]), mean_returns, cov_matrix.reshape(1, 1)
            )
            return {
                "weights": {ticker: 1.0},
                "expected_return": port_return,
                "volatility": port_vol,
                "sharpe_ratio": sharpe,
            }

        n = len(surviving)
        w0 = np.ones(n) / n

        def objective(w):
            port_return = np.dot(w, mean_returns)
            port_var = np.dot(w, np.dot(cov_matrix, w))
            return (1.0 - rt) * (-port_return) + rt * port_var

        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        bounds = [(0.0, 1.0)] * n

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 1000},
        )

        if not result.success:
            return _EMPTY_PORTFOLIO.copy()

        # Post-process: enforce minimum weight floor so every ticker gets some allocation
        min_w = max(0.02, 1.0 / (n * 4))
        raw = np.maximum(result.x, min_w)
        raw = np.clip(raw, min_w, 0.80)
        raw = raw / raw.sum()  # re-normalise to sum=1

        weights_dict = {t: float(w) for t, w in zip(surviving, raw)}
        weights_array = np.array([weights_dict[t] for t in surviving])
        port_return, port_vol, sharpe = _compute_stats(
            weights_array, mean_returns, cov_matrix
        )

        return {
            "weights": weights_dict,
            "expected_return": port_return,
            "volatility": port_vol,
            "sharpe_ratio": sharpe,
        }

    except Exception:
        return _EMPTY_PORTFOLIO.copy()
