"""Tests for data/reasoning_log.py — no Ollama, no network required."""
from datetime import datetime, timezone

import pytest

from data.decision_engine import AxisScore
from data.founder_data import FounderProfile
from data.reasoning_log import ReasoningLog, build_screening_log
from data.risk_flags import RiskFlag
from data.scoring_engine import ScreeningResult
from data.trust_score import Claim, VerifiedClaim


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _profile() -> FounderProfile:
    return FounderProfile(
        name="Test Founder",
        company="TestCo",
        sector="AI/ML",
        stage="seed",
        github_url=None,
        key_signals={"commit_frequency": 8, "total_stars": 100},
    )


def _axis(name: str, score: float = 72.0, trend: str = "stable",
          evidence: list = None) -> AxisScore:
    return AxisScore(
        name=name,
        score=score,
        trend=trend,
        rationale="test rationale",
        evidence=evidence if evidence is not None else [f"{name}: signal={score}"],
    )


def _screening(risk_flags=None) -> ScreeningResult:
    return ScreeningResult(
        profile=_profile(),
        founder_axis=_axis("founder", 75, "improving", ["commit_frequency=8 → bullish"]),
        market_axis=_axis("market", 68, "stable", ["sector=AI/ML → neutral"]),
        idea_vs_market_axis=_axis("idea_vs_market", 80, "improving", ["strong product fit"]),
        risk_flags=risk_flags or [],
        thesis_match=True,
        thesis_reason="Sector and stage match thesis config.",
    )


def _claim(text: str, category: str = "traction") -> Claim:
    return Claim(
        claim_text=text,
        category=category,
        confidence_score=0.9,
        source_reference="pitch_deck_text",
    )


def _verified(claim: Claim, status: str = "verified",
              contradiction_note: str = "") -> VerifiedClaim:
    return VerifiedClaim(
        claim=claim,
        status=status,
        verification_confidence=0.85 if status == "verified" else 0.4,
        contradiction_note=contradiction_note,
    )


def _risk_flag(category: str = "traction", severity: str = "high",
               description: str = "Stars vs users mismatch detected") -> RiskFlag:
    return RiskFlag(category=category, severity=severity, description=description)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_axis_steps_present():
    log = build_screening_log(_profile(), _screening(), [], founder_id=0)
    axis_agents = {s.agent for s in log.steps}
    assert "founder" in axis_agents
    assert "market" in axis_agents
    assert "idea_vs_market" in axis_agents


def test_axis_data_point_is_not_empty():
    log = build_screening_log(_profile(), _screening(), [], founder_id=0)
    axis_steps = [s for s in log.steps if s.agent in ("founder", "market", "idea_vs_market")]
    assert len(axis_steps) == 3
    for step in axis_steps:
        assert step.data_point.strip() != "", f"data_point is empty for axis step: {step.agent}"


def test_risk_flag_step_present():
    flags = [_risk_flag("traction", "high", "total_stars=2 contradicts 300k user claim")]
    log = build_screening_log(_profile(), _screening(risk_flags=flags), [], founder_id=1)
    risk_steps = [s for s in log.steps if s.agent == "RiskScanner"]
    assert len(risk_steps) == 1
    assert "traction" in risk_steps[0].conclusion


def test_claim_step_for_non_gap_claim():
    claims = [_verified(_claim("We have 10,000 active users."))]
    log = build_screening_log(_profile(), _screening(), claims, founder_id=2)
    trust_steps = [s for s in log.steps if s.agent == "TrustScorer"]
    assert len(trust_steps) == 1


def test_contradicted_claim_conclusion_contains_contradicted():
    c = _claim("We have 200,000 users and 3 GitHub stars.")
    vc = _verified(c, status="contradicted",
                   contradiction_note="total_stars=3 contradicts 200k user claim")
    log = build_screening_log(_profile(), _screening(), [vc], founder_id=3)
    trust_steps = [s for s in log.steps if s.agent == "TrustScorer"]
    assert any("contradicted" in s.conclusion for s in trust_steps)


def test_contradicted_claim_data_point_cites_contradiction_note():
    c = _claim("We have 200,000 users and 3 GitHub stars.")
    note = "total_stars=3 contradicts 200k user claim — high risk of fabrication"
    vc = _verified(c, status="contradicted", contradiction_note=note)
    log = build_screening_log(_profile(), _screening(), [vc], founder_id=3)
    trust_steps = [s for s in log.steps if s.agent == "TrustScorer"]
    assert any(note[:50] in s.data_point for s in trust_steps)


def test_gap_claim_not_emitted_as_step():
    gap = _verified(_claim("not disclosed", category="revenue"))
    real = _verified(_claim("500K active users on platform."))
    log = build_screening_log(_profile(), _screening(), [gap, real], founder_id=4)
    trust_steps = [s for s in log.steps if s.agent == "TrustScorer"]
    assert len(trust_steps) == 1
    assert "500K" in trust_steps[0].conclusion or "500K" in trust_steps[0].data_point


def test_empty_verified_claims_still_returns_valid_log():
    log = build_screening_log(_profile(), _screening(), [], founder_id=5)
    assert isinstance(log, ReasoningLog)
    assert len(log.steps) >= 3


def test_no_placeholder_data_points():
    placeholder_claims = [
        _verified(_claim("Placeholder revenue figure")),
        _verified(_claim("TODO: fill in user count")),
        _verified(_claim("N/A for this market")),
    ]
    log = build_screening_log(_profile(), _screening(), placeholder_claims, founder_id=6)
    bad_words = {"placeholder", "todo", "n/a"}
    for step in log.steps:
        dp_lower = step.data_point.lower()
        has_bad = any(w in dp_lower for w in bad_words)
        assert not has_bad, f"Placeholder word found in data_point for step {step.step_number}: {step.data_point!r}"


def test_founder_id_matches_input():
    log = build_screening_log(_profile(), _screening(), [], founder_id=42)
    assert log.founder_id == 42


def test_timestamp_is_iso_format():
    log = build_screening_log(_profile(), _screening(), [], founder_id=0)
    ts = log.timestamp
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None, "timestamp must be timezone-aware"
