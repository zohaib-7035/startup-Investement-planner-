"""Tests for data/memo_generator.py v2 — MemoSection-based interface."""
import json
import re
from unittest.mock import MagicMock, patch

from data.decision_engine import AxisScore
from data.founder_data import FounderProfile
from data.memo_generator import (
    NOT_DISCLOSED,
    InvestmentMemo,
    MemoSection,
    export_memo_markdown,
    export_memo_pdf,
    generate_memo,
)
from data.risk_flags import RiskFlag
from data.scoring_engine import ScreeningResult
from data.trust_score import Claim, VerifiedClaim


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _verified_claim(text: str, category: str = "traction") -> VerifiedClaim:
    return VerifiedClaim(
        claim=Claim(
            claim_text=text,
            category=category,
            confidence_score=0.8,
            source_reference="pitch_deck",
        ),
        status="verified",
        verification_confidence=0.8,
        supporting_evidence=["test signal"],
    )


def _unverifiable_claim(text: str = "not disclosed", category: str = "other") -> VerifiedClaim:
    return VerifiedClaim(
        claim=Claim(
            claim_text=text,
            category=category,
            confidence_score=1.0,
            source_reference="gap",
        ),
        status="unverifiable",
        verification_confidence=1.0,
        supporting_evidence=["Gap flagged: data absent from profile"],
    )


def _axis(name: str, score: float = 70.0) -> AxisScore:
    return AxisScore(
        name=name,
        score=score,
        trend="stable",
        rationale=f"{name} looks promising",
        evidence=[f"{name} evidence item 1"],
    )


def _minimal_screening(profile: FounderProfile) -> ScreeningResult:
    return ScreeningResult(
        profile=profile,
        founder_axis=_axis("Founder"),
        market_axis=_axis("Market"),
        idea_vs_market_axis=_axis("Idea vs Market"),
        risk_flags=[],
        thesis_match=True,
        thesis_reason="Meets investment criteria",
    )


def _minimal_profile() -> FounderProfile:
    return FounderProfile(
        name="Test Founder",
        company="TestCo",
        sector="SaaS",
        stage="seed",
        github_url="https://github.com/testco",
        key_signals={"contributor_count": 3},
        raw_sources=[],
    )


def _rich_verified_claims() -> list:
    return [
        _verified_claim("20K active users on platform", "traction"),
        _verified_claim("team of 3 engineers", "team"),
        _verified_claim("$5B TAM in enterprise SaaS", "market_size"),
        _unverifiable_claim("not disclosed", "other"),
    ]


# ---------------------------------------------------------------------------
# Sentinel constant
# ---------------------------------------------------------------------------

def test_not_disclosed_sentinel_exact_value():
    assert NOT_DISCLOSED == "[Not Disclosed]"


# ---------------------------------------------------------------------------
# Required sections — structure
# ---------------------------------------------------------------------------

def test_generate_memo_returns_investment_memo():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    assert isinstance(memo, InvestmentMemo)


def test_generate_memo_has_exactly_5_required_sections():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    assert len(memo.required_sections) == 5


def test_required_sections_all_have_non_empty_content():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    for section in memo.required_sections:
        assert section.content, f"Section '{section.title}' has empty content"


def test_required_sections_all_memo_section_type():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    for section in memo.required_sections:
        assert isinstance(section, MemoSection)


def test_required_sections_have_expected_titles():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    titles = [s.title for s in memo.required_sections]
    for expected in ("Company Snapshot", "Investment Hypotheses", "SWOT", "Problem & Product", "Traction & KPIs"):
        assert any(expected in t for t in titles), f"Missing required section: {expected}"


# ---------------------------------------------------------------------------
# Empty-claims guard — no required section may have claims=[]
# ---------------------------------------------------------------------------

def test_no_required_section_has_empty_claims_list():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    for section in memo.required_sections:
        assert len(section.claims) > 0, f"Section '{section.title}' has empty claims list"


def test_no_required_section_has_empty_claims_when_no_verified_claims():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), [])
    for section in memo.required_sections:
        assert len(section.claims) > 0, f"Section '{section.title}' has empty claims list (no-claim input)"


def test_claims_guard_on_traction_unavailable():
    profile = _minimal_profile()
    # Pass no traction/revenue claims
    claims = [_verified_claim("team of 3", "team")]
    memo = generate_memo(profile, _minimal_screening(profile), claims)
    traction = next(s for s in memo.required_sections if "Traction" in s.title)
    assert len(traction.claims) > 0


# ---------------------------------------------------------------------------
# Optional sections — "not disclosed" flagging
# ---------------------------------------------------------------------------

def test_optional_financials_not_available_when_no_revenue_claim():
    profile = _minimal_profile()
    # No revenue claims
    claims = [_verified_claim("team of 3", "team")]
    memo = generate_memo(profile, _minimal_screening(profile), claims)
    financials = next((s for s in memo.optional_sections if "Financials" in s.title), None)
    assert financials is not None
    assert financials.is_available is False
    assert "not disclosed" in (financials.unavailability_reason or "")


def test_optional_cap_table_not_available_by_default():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), [])
    cap_table = next((s for s in memo.optional_sections if "Cap Table" in s.title), None)
    assert cap_table is not None
    assert cap_table.is_available is False


def test_optional_due_diligence_always_not_available():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    dd = next((s for s in memo.optional_sections if "Due Diligence" in s.title), None)
    assert dd is not None
    assert dd.is_available is False


def test_optional_exit_perspective_always_not_available():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    ep = next((s for s in memo.optional_sections if "Exit" in s.title), None)
    assert ep is not None
    assert ep.is_available is False


# ---------------------------------------------------------------------------
# overall_trust_score
# ---------------------------------------------------------------------------

def test_overall_trust_score_is_mean_of_verification_confidences():
    profile = _minimal_profile()
    claims = [
        _verified_claim("claim A"),
        _verified_claim("claim B"),
    ]
    # Both have verification_confidence=0.8 → mean = 0.8
    memo = generate_memo(profile, _minimal_screening(profile), claims)
    assert abs(memo.overall_trust_score - 0.8) < 0.01


def test_overall_trust_score_defaults_to_zero_on_empty_claims():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), [])
    assert memo.overall_trust_score == 0.0


def test_overall_trust_score_in_range():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    assert 0.0 <= memo.overall_trust_score <= 1.0


# ---------------------------------------------------------------------------
# export_memo_markdown — structure
# ---------------------------------------------------------------------------

def test_export_memo_markdown_returns_string():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    assert isinstance(export_memo_markdown(memo), str)


def test_export_memo_markdown_contains_company_name():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    md = export_memo_markdown(memo)
    assert "TestCo" in md


def test_export_memo_markdown_contains_trust_score_header():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    md = export_memo_markdown(memo)
    assert "Trust Score:" in md


def test_export_memo_markdown_contains_all_5_required_headings():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    md = export_memo_markdown(memo)
    for title in ("Company Snapshot", "Investment Hypotheses", "SWOT", "Problem & Product", "Traction & KPIs"):
        assert title in md, f"Missing required heading: {title}"


def test_export_memo_markdown_contains_not_disclosed_for_unavailable_sections():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), [])
    md = export_memo_markdown(memo)
    assert "not disclosed" in md.lower() or NOT_DISCLOSED.lower() in md.lower()


def test_export_memo_markdown_contains_traceability_table():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    md = export_memo_markdown(memo)
    assert "Claim Traceability" in md
    assert "| Claim |" in md


def test_export_memo_markdown_never_raises():
    # Even on a degenerate memo
    empty_memo = InvestmentMemo(
        company="X",
        date="2026-01-01",
        required_sections=[],
        optional_sections=[],
        overall_trust_score=0.0,
    )
    result = export_memo_markdown(empty_memo)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# No fabricated data test (named standalone test — canvas safeguard)
# ---------------------------------------------------------------------------

def test_no_fabricated_revenue_figures_in_memo_without_revenue_claims():
    profile = _minimal_profile()
    # Only team claim — no revenue or traction claims
    claims = [_verified_claim("team of 3 engineers", "team")]
    memo = generate_memo(profile, _minimal_screening(profile), claims)
    md = export_memo_markdown(memo)
    # Pattern: dollar amounts, euro amounts, digit+K/M/B followed by ARR/MRR/revenue
    assert re.search(r"\$\d|\€\d|£\d|\d+[KMBkmb]\s*(ARR|MRR|revenue)", md) is None, (
        "Fabricated revenue figure detected in memo output — content must trace to a VerifiedClaim"
    )


# ---------------------------------------------------------------------------
# export_memo_pdf
# ---------------------------------------------------------------------------

def test_export_memo_pdf_returns_bytes():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    result = export_memo_pdf(memo)
    assert isinstance(result, bytes)


def test_export_memo_pdf_returns_non_empty_bytes():
    profile = _minimal_profile()
    memo = generate_memo(profile, _minimal_screening(profile), _rich_verified_claims())
    result = export_memo_pdf(memo)
    assert len(result) > 0


def test_export_memo_pdf_never_raises():
    empty_memo = InvestmentMemo(
        company="X",
        date="2026-01-01",
        required_sections=[],
        optional_sections=[],
        overall_trust_score=0.0,
    )
    result = export_memo_pdf(empty_memo)
    assert isinstance(result, bytes)  # may be b"" if reportlab errors, but must not raise


# ---------------------------------------------------------------------------
# End-to-end — Sofia / DeployKit from sample_founders.json
# ---------------------------------------------------------------------------

def test_end_to_end_sofia_deploykit():
    from data.sourcing import load_sample_founders
    founders = load_sample_founders()
    sofia = next((f for f in founders if f.company == "DeployKit"), None)
    assert sofia is not None, "DeployKit not found in sample_founders.json"

    screening = _minimal_screening(sofia)

    # Mock Ollama — return a single traction claim
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": json.dumps([
            {
                "claim_text": "210 stars on GitHub",
                "category": "traction",
                "confidence_score": 0.75,
                "source_reference": "pitch_deck",
            }
        ])}
    }
    with patch("data.trust_score.requests.post", return_value=mock_resp):
        from data.trust_score import extract_claims, verify_claim
        claims = extract_claims(sofia)

    evidence = [
        {"signal": "total_stars", "score": sofia.key_signals.get("total_stars", 0), "direction": "neutral"}
    ]
    verified = [verify_claim(c, evidence) for c in claims]

    memo = generate_memo(sofia, screening, verified)
    md = export_memo_markdown(memo)

    # All 5 required headings present
    for title in ("Company Snapshot", "Investment Hypotheses", "SWOT", "Problem & Product", "Traction & KPIs"):
        assert title in md, f"Missing required heading in Sofia memo: {title}"

    # Trust score header present
    assert "Trust Score:" in md

    # At least one "not disclosed" label (cap table, financials, etc.)
    assert "not disclosed" in md.lower() or NOT_DISCLOSED in md
