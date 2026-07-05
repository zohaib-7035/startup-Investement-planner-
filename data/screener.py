import math

_CONFIDENCE_MAP = {"BUY": 0.85, "SELL": 0.75, "HOLD": 0.50}

_INVALID_RSI_FALLBACK = {
    "action": "HOLD",
    "confidence": 0.0,
    "reason": "RSI value is missing or invalid.",
}


def _safe_rsi(value) -> "float | None":
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v < 0 or v > 100:
        return None
    return v


def generate_recommendation(rsi, eps_surprise, pe_ratio) -> dict:
    """Apply rule-based screener to return Buy/Hold/Sell recommendation. Never raises."""
    validated_rsi = _safe_rsi(rsi)
    if validated_rsi is None:
        return _INVALID_RSI_FALLBACK.copy()

    if validated_rsi < 30 and eps_surprise is not None and eps_surprise > 0:
        action = "BUY"
        reason = (
            f"RSI is oversold at {validated_rsi:.1f} and EPS surprise is positive "
            f"({eps_surprise:+.2f}), indicating undervalued momentum."
        )
    elif validated_rsi > 70:
        action = "SELL"
        reason = (
            f"RSI is overbought at {validated_rsi:.1f}, indicating the stock may be overextended."
        )
    else:
        action = "HOLD"
        reason = (
            f"No strong signal: RSI is {validated_rsi:.1f} and conditions for BUY or SELL are not met."
        )

    return {"action": action, "confidence": _CONFIDENCE_MAP[action], "reason": reason}
