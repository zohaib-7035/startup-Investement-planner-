import math

import numpy as np

_EMPTY_RESULT = {
    "var_1w_95": None,
    "cvar_1w_95": None,
    "portfolio_volatility": None,
    "concentration_risk": None,
    "risk_level": None,
    "warnings": None,
}

# (var_threshold, concentration_threshold, label) — checked Critical → High → Medium
_RISK_THRESHOLDS = [
    (0.10, 0.60, "Critical"),
    (0.05, 0.40, "High"),
    (0.02, 0.25, "Medium"),
]


def _build_portfolio_series(weights, returns_data):
    surviving = [t for t in weights if t in returns_data and returns_data[t]]
    if not surviving:
        return None

    date_to_prices = {}
    for ticker in surviving:
        for row in returns_data[ticker]:
            date = row.get("date")
            close = row.get("close")
            if date is None or close is None:
                continue
            if date not in date_to_prices:
                date_to_prices[date] = {}
            date_to_prices[date][ticker] = float(close)

    common_dates = sorted(
        d for d, prices in date_to_prices.items() if len(prices) == len(surviving)
    )
    if len(common_dates) < 2:
        return None

    price_matrix = np.array(
        [[date_to_prices[d][t] for t in surviving] for d in common_dates],
        dtype=float,
    )
    log_returns = np.log(price_matrix[1:] / price_matrix[:-1])

    raw_w = np.array([weights[t] for t in surviving], dtype=float)
    total_w = raw_w.sum()
    if total_w == 0.0:
        return None
    norm_w = raw_w / total_w

    return log_returns.dot(norm_w)


def _compute_var_cvar(portfolio_series, confidence_level, horizon_days):
    q = (1.0 - confidence_level) * 100.0
    daily_var = float(abs(np.percentile(portfolio_series, q)))

    tail = portfolio_series[portfolio_series <= -daily_var]
    daily_cvar = float(abs(np.mean(tail))) if tail.size > 0 else daily_var

    scale = math.sqrt(horizon_days)
    return float(daily_var * scale), float(daily_cvar * scale)


def _compute_concentration(weights):
    return float(sum(w * w for w in weights.values()))


def _classify_risk_level(var_1w, concentration):
    for var_t, conc_t, label in _RISK_THRESHOLDS:
        if var_1w >= var_t or concentration >= conc_t:
            return label
    return "Low"


def _build_warnings(var_1w, concentration, n_tickers):
    warnings = []
    if n_tickers == 1:
        warnings.append("Single asset portfolio: maximum concentration risk.")
    if concentration > 0.40:
        warnings.append(
            f"High concentration risk: HHI = {concentration:.2f}. Consider diversifying."
        )
    if var_1w > 0.05:
        warnings.append(
            f"Elevated VaR: 1-week 95% VaR = {var_1w:.1%}. Significant downside risk."
        )
    return warnings


def calculate_risk_metrics(weights, returns_data, confidence_level=0.95, horizon_days=5) -> dict:
    """
    Calculate portfolio risk metrics from pre-fetched price data.
    Returns {var_1w_95, cvar_1w_95, portfolio_volatility, concentration_risk,
             risk_level, warnings}. Never raises.
    """
    try:
        if not isinstance(weights, dict) or not weights:
            return _EMPTY_RESULT.copy()
        if not isinstance(returns_data, dict) or not returns_data:
            return _EMPTY_RESULT.copy()
        try:
            cl = float(confidence_level)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if not (0.0 < cl < 1.0):
            return _EMPTY_RESULT.copy()
        try:
            hd = float(horizon_days)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if not math.isfinite(hd) or hd <= 0:
            return _EMPTY_RESULT.copy()

        series = _build_portfolio_series(weights, returns_data)
        if series is None or len(series) < 2:
            return _EMPTY_RESULT.copy()

        var_1w, cvar_1w = _compute_var_cvar(series, cl, hd)
        concentration = _compute_concentration(weights)
        port_vol = float(np.std(series, ddof=1) * math.sqrt(252))
        risk_level = _classify_risk_level(var_1w, concentration)
        warnings = _build_warnings(var_1w, concentration, len(weights))

        return {
            "var_1w_95": var_1w,
            "cvar_1w_95": cvar_1w,
            "portfolio_volatility": port_vol,
            "concentration_risk": concentration,
            "risk_level": risk_level,
            "warnings": warnings,
        }

    except Exception:
        return _EMPTY_RESULT.copy()
