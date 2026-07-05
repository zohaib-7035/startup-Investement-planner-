_EMPTY_RESULT = {
    "final_action": "HOLD",
    "confidence": 0.0,
    "reasoning": "",
    "conflicts": [],
}

_SIGNAL_AGENT_KEYS = ("technical", "signals", "fundamentals", "sentiment", "macro")

_VALID_ACTIONS = frozenset({"BUY", "SELL", "HOLD"})

_RISK_PENALTIES = {
    "LOW": 1.0,
    "MEDIUM": 1.0,
    "HIGH": 0.80,
    "CRITICAL": 0.60,
}


def _parse_agent_entry(name, entry):
    if not isinstance(entry, dict):
        return None
    action = entry.get("action")
    confidence = entry.get("confidence")
    if not isinstance(action, str) or action not in _VALID_ACTIONS:
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    confidence = float(confidence)
    if confidence < 0.0 or confidence > 1.0:
        return None
    return (name, action, confidence)


def _weighted_vote(parsed_entries):
    totals = {}
    for _, action, confidence in parsed_entries:
        totals[action] = totals.get(action, 0.0) + confidence
    if not totals:
        return "HOLD", totals
    buy_weight = totals.get("BUY", 0.0)
    sell_weight = totals.get("SELL", 0.0)
    if buy_weight == sell_weight and buy_weight > 0.0:
        return "HOLD", totals
    return max(totals, key=lambda a: totals[a]), totals


def _compute_confidence(parsed_entries, winning_action, penalty):
    winners = [c for _, a, c in parsed_entries if a == winning_action]
    if not winners:
        return 0.0
    raw = sum(winners) / len(winners)
    return float(min(1.0, max(0.0, raw * penalty)))


def _detect_conflicts(parsed_entries, final_action):
    return [
        f"{name}: {action} (confidence {confidence:.2f})"
        for name, action, confidence in parsed_entries
        if action != final_action
    ]


def _build_reasoning(parsed_entries, final_action, pre_penalty_conf, risk_level, penalty):
    votes = ", ".join(
        f"{name}={action}/{confidence:.2f}"
        for name, action, confidence in parsed_entries
    )
    penalty_str = f"{penalty:.2f}" if penalty != 1.0 else "none"
    return (
        f"Votes: {votes}. "
        f"Winner: {final_action} (pre-penalty confidence {pre_penalty_conf:.4f}). "
        f"Risk: {risk_level or 'UNKNOWN'} (penalty {penalty_str})."
    )


def aggregate_signals(agent_outputs) -> dict:
    try:
        if not isinstance(agent_outputs, dict):
            return _EMPTY_RESULT.copy()
        parsed_entries = []
        for key in _SIGNAL_AGENT_KEYS:
            entry = agent_outputs.get(key)
            parsed = _parse_agent_entry(key, entry)
            if parsed is not None:
                parsed_entries.append(parsed)
        if not parsed_entries:
            return _EMPTY_RESULT.copy()
        risk_dict = agent_outputs.get("risk")
        risk_level = risk_dict.get("level") if isinstance(risk_dict, dict) else None
        penalty = _RISK_PENALTIES.get(risk_level, 1.0)
        final_action, _totals = _weighted_vote(parsed_entries)
        pre_penalty_conf = _compute_confidence(parsed_entries, final_action, 1.0)
        confidence = _compute_confidence(parsed_entries, final_action, penalty)
        conflicts = _detect_conflicts(parsed_entries, final_action)
        reasoning = _build_reasoning(
            parsed_entries, final_action, pre_penalty_conf, risk_level, penalty
        )
        return {
            "final_action": final_action,
            "confidence": confidence,
            "reasoning": reasoning,
            "conflicts": conflicts,
        }
    except Exception:
        return _EMPTY_RESULT.copy()
