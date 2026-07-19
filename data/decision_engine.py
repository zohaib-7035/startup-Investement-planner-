"""
Decision Engine — aggregates three independent scoring axes into a DecisionResult.
The three axes (Founder / Market / Idea-vs-Market) are NEVER averaged or merged.
Each axis keeps its own score, trend, and rationale in the output.
Never raises.
"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional
from data.founder_data import FounderProfile


@dataclass
class AxisScore:
    name: str
    score: float
    trend: Literal["improving", "declining", "stable"]
    rationale: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    axes: List[AxisScore] = field(default_factory=list)
    overall_verdict: str = "WATCHLIST"
    memo_inputs: dict = field(default_factory=dict)
    # NOTE: intentionally NO top-level `score` field — axes are never averaged


def compute_founder_axis(profile: FounderProfile) -> AxisScore:
    """Score the Founder axis — delegates to scoring_engine."""
    from data.scoring_engine import score_founder_axis
    return score_founder_axis(profile)


def compute_market_axis(profile: FounderProfile) -> AxisScore:
    """Score the Market axis — delegates to scoring_engine."""
    from data.scoring_engine import score_market_axis
    return score_market_axis(profile)


def compute_idea_axis(profile: FounderProfile) -> AxisScore:
    """Score the Idea-vs-Market fit axis — delegates to scoring_engine."""
    from data.scoring_engine import score_idea_vs_market_axis
    return score_idea_vs_market_axis(profile)


def make_decision(
    founder_axis: Optional[AxisScore],
    market_axis: Optional[AxisScore],
    idea_axis: Optional[AxisScore],
    thesis_result=None,
    risk_flags: Optional[list] = None,
) -> DecisionResult:
    """
    Assemble three independent AxisScore objects into a DecisionResult.
    Axes are never averaged — each keeps its own score and trend.
    Returns DecisionResult. Never raises.
    """
    try:
        axes = [a for a in (founder_axis, market_axis, idea_axis) if a is not None]

        # Derive overall verdict from thesis result if available
        if thesis_result is not None and hasattr(thesis_result, "verdict"):
            overall_verdict = thesis_result.verdict
        elif axes:
            # Simple heuristic: majority of axes above threshold
            passing = sum(1 for a in axes if a.score >= 60.0)
            if passing == len(axes):
                overall_verdict = "PASS"
            elif passing == 0:
                overall_verdict = "FAIL"
            else:
                overall_verdict = "WATCHLIST"
        else:
            overall_verdict = "WATCHLIST"

        memo_inputs = {
            "thesis_verdict":     thesis_result.verdict if thesis_result else None,
            "matched_rules":      thesis_result.matched_rules if thesis_result else [],
            "failed_rules":       thesis_result.failed_rules if thesis_result else [],
            "high_risk_flags":    [
                f.category for f in (risk_flags or []) if f.severity == "high"
            ],
            "total_risk_flags":   len(risk_flags) if risk_flags else 0,
        }

        return DecisionResult(
            axes=axes,
            overall_verdict=overall_verdict,
            memo_inputs=memo_inputs,
        )
    except Exception:
        return DecisionResult()
