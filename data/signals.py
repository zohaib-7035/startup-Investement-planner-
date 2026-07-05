import math

# Op 1 — fallback constant (confidence 0.0 distinguishes invalid HOLD from real HOLD at 0.40)
_INVALID_INPUT_FALLBACK = {
    "action": "HOLD",
    "confidence": 0.0,
    "reason": "Invalid or missing input — one or more parameters failed validation.",
}

# Op 1 — base confidence per action
_CONFIDENCE_MAP = {
    "BUY": 0.85,
    "SELL": 0.75,
    "WATCHLIST": 0.55,
    "HOLD": 0.40,
}

# Op 2 — ATR volatility modifier thresholds
_ATR_HIGH_THRESHOLD = 5.0
_ATR_VOLATILITY_PENALTY = 0.90


# Op 3
def _safe_indicator(value, min_val=None, max_val=None):
    """Return validated float, or None if value is missing, non-numeric, non-finite, or out of bounds."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if min_val is not None and v < min_val:
        return None
    if max_val is not None and v > max_val:
        return None
    return v


# Op 4
def _apply_atr_modifier(confidence, atr):
    """Return confidence reduced by _ATR_VOLATILITY_PENALTY when atr exceeds _ATR_HIGH_THRESHOLD."""
    if atr > _ATR_HIGH_THRESHOLD:
        return confidence * _ATR_VOLATILITY_PENALTY
    return confidence


# Op 5
def generate_advanced_signal(adx, atr, momentum, volume_ratio):
    """
    Return a BUY/SELL/WATCHLIST/HOLD signal dict from ADX, ATR, momentum, and volume_ratio.

    Return schema: {action: str, confidence: float, reason: str}. Never raises.

    Rule set (first match wins):
      1. BUY      — ADX > 25 AND momentum > 0 AND volume_ratio >= 1.5
      2. SELL     — ADX > 25 AND momentum < 0 AND volume_ratio >= 1.5
      3. WATCHLIST — 20 <= ADX <= 25 (emerging trend)
      4. HOLD     — all other cases

    ATR > 5.0 reduces confidence by 10% (multiplied by 0.90) to reflect elevated volatility risk.
    This penalty applies to all four actions.

    WATCHLIST is not in meta_agent._VALID_ACTIONS — callers must handle WATCHLIST
    before passing the result to aggregate_signals, or it will be silently dropped.
    """
    try:
        safe_adx = _safe_indicator(adx, min_val=0.0, max_val=100.0)
        safe_atr = _safe_indicator(atr, min_val=0.0)
        safe_momentum = _safe_indicator(momentum)
        safe_volume_ratio = _safe_indicator(volume_ratio, min_val=0.0)

        if any(v is None for v in (safe_adx, safe_atr, safe_momentum, safe_volume_ratio)):
            return dict(_INVALID_INPUT_FALLBACK)

        if safe_adx > 25.0 and safe_momentum > 0.0 and safe_volume_ratio >= 1.5:
            action = "BUY"
            reason = (
                f"Strong uptrend: ADX {safe_adx:.1f} > 25, "
                f"positive momentum {safe_momentum:.4f}, "
                f"volume confirmed (ratio {safe_volume_ratio:.2f})."
            )
        elif safe_adx > 25.0 and safe_momentum < 0.0 and safe_volume_ratio >= 1.5:
            action = "SELL"
            reason = (
                f"Strong downtrend: ADX {safe_adx:.1f} > 25, "
                f"negative momentum {safe_momentum:.4f}, "
                f"volume confirmed (ratio {safe_volume_ratio:.2f})."
            )
        elif 20.0 <= safe_adx <= 25.0:
            action = "WATCHLIST"
            reason = (
                f"Emerging trend: ADX {safe_adx:.1f} in 20–25 range — "
                "watch for volume and momentum confirmation before acting."
            )
        else:
            action = "HOLD"
            reason = (
                f"No clear signal: ADX {safe_adx:.1f} below trend threshold "
                "or insufficient volume/momentum confirmation."
            )

        confidence = _apply_atr_modifier(_CONFIDENCE_MAP[action], safe_atr)
        return {"action": action, "confidence": confidence, "reason": reason}
    except Exception:
        return dict(_INVALID_INPUT_FALLBACK)
