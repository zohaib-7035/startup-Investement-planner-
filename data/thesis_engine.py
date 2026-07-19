"""
Thesis Engine — configurable investor thesis filter.
Every verdict cites the name of the rule it matched or failed.
Never raises.
"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional
from data.founder_data import FounderProfile


@dataclass
class ThesisConfig:
    sectors: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    geographies: List[str] = field(default_factory=list)
    check_size_min: int = 0
    check_size_max: int = 10_000_000
    min_ownership_pct: float = 0.0
    risk_appetite: Literal["low", "medium", "high"] = "medium"


@dataclass
class ThesisResult:
    verdict: Literal["PASS", "FAIL", "WATCHLIST"] = "WATCHLIST"
    matched_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    score: float = 0.0


def _rule_sector_match(profile: FounderProfile, config: ThesisConfig) -> Optional[bool]:
    if not config.sectors:
        return None  # no constraint = skip rule
    return profile.sector in config.sectors


def _rule_stage_match(profile: FounderProfile, config: ThesisConfig) -> Optional[bool]:
    if not config.stages:
        return None
    return profile.stage in config.stages


def _rule_geography_match(profile: FounderProfile, config: ThesisConfig) -> Optional[bool]:
    if not config.geographies:
        return None
    geo = (profile.key_signals or {}).get("geography")
    return geo in config.geographies if geo else False


def _rule_risk_appetite_match(profile: FounderProfile, config: ThesisConfig) -> Optional[bool]:
    """Low risk appetite rejects solo founders (contributor_count == 1)."""
    if config.risk_appetite == "low":
        contributor_count = (profile.key_signals or {}).get("contributor_count")
        if contributor_count is not None and contributor_count < 2:
            return False
    return None  # other appetites have no hard rule here


_BLOCKING_RULES = {
    "sector_match":       _rule_sector_match,
    "stage_match":        _rule_stage_match,
    "geography_match":    _rule_geography_match,
    "risk_appetite_match": _rule_risk_appetite_match,
}


def evaluate_founder(profile: FounderProfile, config: ThesisConfig) -> ThesisResult:
    """
    Evaluate a FounderProfile against a ThesisConfig.
    Every verdict line names the rule that matched or failed.
    Returns ThesisResult. Never raises.
    """
    try:
        matched: List[str] = []
        failed: List[str] = []

        for rule_name, rule_fn in _BLOCKING_RULES.items():
            result = rule_fn(profile, config)
            if result is None:
                continue  # rule not applicable — skip
            if result:
                matched.append(rule_name)
            else:
                failed.append(rule_name)

        total = len(matched) + len(failed)
        score = round(len(matched) / total, 4) if total > 0 else 1.0

        if failed:
            verdict: Literal["PASS", "FAIL", "WATCHLIST"] = "FAIL"
        elif matched:
            verdict = "PASS"
        else:
            verdict = "WATCHLIST"

        return ThesisResult(
            verdict=verdict,
            matched_rules=matched,
            failed_rules=failed,
            score=score,
        )
    except Exception:
        return ThesisResult(
            verdict="WATCHLIST",
            matched_rules=[],
            failed_rules=[],
            score=0.0,
        )
