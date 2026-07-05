_EMPTY_PROFILES_RESULT = {}

_DEFAULT_PROFILES = [
    {"name": "conservative", "risk_tol": 0.2},
    {"name": "balanced", "risk_tol": 0.5},
    {"name": "aggressive", "risk_tol": 0.9},
]

_VOLATILITY_MODIFIERS = {
    "HIGH": 0.5,
    "MEDIUM": 0.75,
    "LOW": 1.0,
}

_VALID_SIGNALS = frozenset({"BUY", "SELL", "HOLD"})

_BASE_SIZES = {
    "BUY": 1.0,
    "SELL": 0.0,
    "HOLD": 0.0,
}

_BUY_THRESHOLD = 0.3


def _validate_profile(profile):
    if not isinstance(profile, dict):
        return None
    name = profile.get("name")
    if not isinstance(name, str) or not name:
        return None
    risk_tol = profile.get("risk_tol")
    if isinstance(risk_tol, bool):
        return None
    if not isinstance(risk_tol, (int, float)):
        return None
    risk_tol = float(risk_tol)
    if risk_tol < 0.0 or risk_tol > 1.0:
        return None
    return (name, risk_tol)


def _build_reasoning(ticker, signal, volatility, risk_tol, modifier, position_size, action):
    return (
        f"{str(ticker)} — signal: {signal}, volatility: {volatility} "
        f"(modifier: {modifier:.2f}), risk tolerance: {risk_tol:.2f} "
        f"→ position size: {position_size:.4f} → action: {action}"
    )


def get_profile_recommendations(ticker, signal, volatility, profiles=None):
    try:
        signal = str(signal).upper()
        volatility = str(volatility).upper()

        if signal not in _VALID_SIGNALS:
            return _EMPTY_PROFILES_RESULT.copy()

        modifier = _VOLATILITY_MODIFIERS.get(volatility)
        if modifier is None:
            return _EMPTY_PROFILES_RESULT.copy()

        active_profiles = _DEFAULT_PROFILES if profiles is None else profiles

        result = {}
        for entry in active_profiles:
            validated = _validate_profile(entry)
            if validated is None:
                continue
            name, risk_tol = validated
            raw = _BASE_SIZES[signal] * modifier * risk_tol
            position_size = float(max(0.0, min(1.0, raw)))
            action = "BUY" if position_size > _BUY_THRESHOLD else "HOLD"
            reasoning = _build_reasoning(
                ticker, signal, volatility, risk_tol, modifier, position_size, action
            )
            result[name] = {
                "action": action,
                "position_size": position_size,
                "reasoning": reasoning,
            }

        if not result:
            return _EMPTY_PROFILES_RESULT.copy()

        return result

    except Exception:
        return _EMPTY_PROFILES_RESULT.copy()
