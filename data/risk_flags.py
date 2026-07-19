"""
Risk flag detection — identifies contradictions and red flags in founder claims.
Returns a list of RiskFlag dataclasses. Never raises.
"""
from dataclasses import dataclass
from typing import List, Literal
from data.founder_data import FounderProfile


@dataclass
class RiskFlag:
    category: str
    description: str
    severity: Literal["low", "medium", "high"]


def _flag_solo_founder(profile: FounderProfile, signals: dict) -> List[RiskFlag]:
    contributor_signal = signals.get("contributor_count", {})
    count_score = contributor_signal.get("score")
    raw_count = (profile.key_signals or {}).get("contributor_count")
    if raw_count is not None and raw_count < 2:
        return [RiskFlag(
            category="solo_founder",
            description=f"Only {raw_count} contributor detected in primary repo. Solo founders carry higher execution risk.",
            severity="medium",
        )]
    if count_score is not None and count_score < 20:
        return [RiskFlag(
            category="solo_founder",
            description="Very low contributor count signal — possible solo founder.",
            severity="medium",
        )]
    return []


def _flag_stale_repo(profile: FounderProfile, signals: dict) -> List[RiskFlag]:
    recency_signal = signals.get("recency", {})
    if recency_signal.get("direction") != "bearish":
        return []
    # Only raise high if deck explicitly claims active development
    deck_claims_active = any(
        phrase in " ".join(profile.raw_sources).lower()
        for phrase in ("active", "growing", "launching", "live")
    )
    severity = "high" if deck_claims_active else "medium"
    days = (profile.key_signals or {}).get("recency")
    return [RiskFlag(
        category="stale_repo",
        description=(
            f"Last commit was {days} days ago" if days is not None
            else "No recent commit activity detected"
        ) + (" — contradicts active development claim." if deck_claims_active else "."),
        severity=severity,
    )]


def _flag_missing_data(profile: FounderProfile, signals: dict) -> List[RiskFlag]:
    flags = []
    for key in ("commit_frequency", "star_growth", "contributor_count", "recency", "tech_stack_depth"):
        sig = signals.get(key, {})
        if sig.get("direction") == "unknown":
            flags.append(RiskFlag(
                category="missing_data",
                description=f"Signal '{key}' has no source data — cannot be verified.",
                severity="low",
            ))
    return flags


def _flag_claim_contradiction(profile: FounderProfile, signals: dict) -> List[RiskFlag]:
    claimed_users = (profile.key_signals or {}).get("claimed_users")
    star_signal = signals.get("star_growth", {})
    star_score = star_signal.get("score")
    if (
        claimed_users is not None
        and claimed_users > 10_000
        and star_score is not None
        and star_score < 20
    ):
        return [RiskFlag(
            category="claim_contradiction",
            description=(
                f"Deck claims {claimed_users:,} users but GitHub star signal score is {star_score}/100 — "
                "no observable evidence of traction at that scale."
            ),
            severity="high",
        )]
    return []


def flag_risks(profile: FounderProfile, signals: dict) -> List[RiskFlag]:
    """
    Detect risk flags across four categories.
    Returns an empty list when no flags are triggered. Never returns None. Never raises.
    """
    try:
        flags: List[RiskFlag] = []
        flags.extend(_flag_solo_founder(profile, signals))
        flags.extend(_flag_stale_repo(profile, signals))
        flags.extend(_flag_missing_data(profile, signals))
        flags.extend(_flag_claim_contradiction(profile, signals))
        return flags
    except Exception:
        return []
