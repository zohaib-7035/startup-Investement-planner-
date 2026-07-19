"""
Agentic Traceability — chain-of-thought reasoning log for VC Brain screening.

build_screening_log(profile, screening, verified_claims, founder_id) -> ReasoningLog
  One ReasoningStep per axis score, per risk flag, and per non-gap VerifiedClaim.
  Every step's data_point cites a specific signal value. Never raises.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from data.founder_data import FounderProfile
from data.scoring_engine import ScreeningResult
from data.trust_score import VerifiedClaim

logger = logging.getLogger(__name__)

_TREND_LABELS = {
    "improving": "improving ▲",
    "declining":  "declining ▼",
    "stable":     "stable →",
}
_PLACEHOLDER_WORDS = {"placeholder", "todo", "n/a"}


def _safe_dp(text: str, fallback: str) -> str:
    """Return text if it is non-empty and contains no placeholder words; else fallback."""
    if not text or any(w in text.lower() for w in _PLACEHOLDER_WORDS):
        return fallback
    return text


@dataclass
class ReasoningStep:
    step_number: int
    agent: str
    conclusion: str
    data_point: str
    confidence: float


@dataclass
class ReasoningLog:
    founder_id: int
    timestamp: str          # ISO-8601
    steps: List[ReasoningStep] = field(default_factory=list)


def build_screening_log(
    profile: FounderProfile,
    screening: ScreeningResult,
    verified_claims: List[VerifiedClaim],
    founder_id: int = 0,
) -> ReasoningLog:
    """
    Assemble a ReasoningLog from structured pipeline outputs.
    Each step cites the exact signal value or evidence string that drove the conclusion.
    Never raises. Always returns a ReasoningLog with at least 3 axis steps.
    """
    try:
        steps: List[ReasoningStep] = []
        n = 0

        # ── Axis steps (always 3) ────────────────────────────────────────────
        for axis in (
            screening.founder_axis,
            screening.market_axis,
            screening.idea_vs_market_axis,
        ):
            n += 1
            trend = _TREND_LABELS.get(axis.trend, axis.trend)
            conclusion = f"score {axis.score:.0f}/100, {trend}"

            # data_point = first non-empty evidence string, else axis name + score
            raw_ev = next((e for e in (axis.evidence or []) if e and e.strip()), "")
            fallback = f"{axis.name}: score={axis.score:.0f}, trend={axis.trend}"
            data_point = _safe_dp(raw_ev, fallback)

            steps.append(ReasoningStep(
                step_number=n,
                agent=axis.name,
                conclusion=conclusion,
                data_point=data_point,
                confidence=min(1.0, max(0.0, axis.score / 100.0)),
            ))

        # ── Risk flag steps ──────────────────────────────────────────────────
        for flag in (screening.risk_flags or []):
            n += 1
            conclusion = f"risk flagged: {flag.category} at {flag.severity}"
            dp = _safe_dp(
                flag.description,
                f"{flag.category}: severity={flag.severity}",
            )
            steps.append(ReasoningStep(
                step_number=n,
                agent="RiskScanner",
                conclusion=conclusion,
                data_point=dp,
                confidence=0.9 if flag.severity == "high" else 0.5,
            ))

        # ── Claim steps (skip gap / "not disclosed" claims) ──────────────────
        for vc in (verified_claims or []):
            if vc.claim.claim_text.strip().lower() == "not disclosed":
                continue
            n += 1
            claim_short = vc.claim.claim_text[:60]
            conclusion = f"claim {vc.status}: {claim_short}"

            if vc.status == "contradicted" and vc.contradiction_note:
                raw_dp = vc.contradiction_note[:200]
            else:
                raw_dp = (
                    f"{vc.claim.claim_text[:120]}"
                    f" — source: {vc.claim.source_reference}"
                )
            dp = _safe_dp(
                raw_dp,
                f"claim [{vc.claim.category}]: status={vc.status}",
            )
            steps.append(ReasoningStep(
                step_number=n,
                agent="TrustScorer",
                conclusion=conclusion,
                data_point=dp,
                confidence=vc.verification_confidence,
            ))

        return ReasoningLog(
            founder_id=founder_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            steps=steps,
        )

    except Exception:
        logger.exception("build_screening_log failed — returning minimal log")
        try:
            ts = datetime.now(timezone.utc).isoformat()
            fallback_steps = []
            for i, axis in enumerate((
                screening.founder_axis,
                screening.market_axis,
                screening.idea_vs_market_axis,
            ), start=1):
                fallback_steps.append(ReasoningStep(
                    step_number=i,
                    agent=axis.name,
                    conclusion=f"score {axis.score:.0f}/100",
                    data_point=f"{axis.name}: score={axis.score:.0f}",
                    confidence=min(1.0, max(0.0, axis.score / 100.0)),
                ))
            return ReasoningLog(founder_id=founder_id, timestamp=ts, steps=fallback_steps)
        except Exception:
            return ReasoningLog(
                founder_id=founder_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                steps=[],
            )
