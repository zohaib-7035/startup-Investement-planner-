"""Tests for data/trust_score.py — all Ollama calls mocked."""
import json
from unittest.mock import MagicMock, patch

import pytest

from data.founder_data import FounderProfile
from data.trust_score import (
    Claim,
    VerifiedClaim,
    extract_claims,
    verify_claim,
    _GAP_SECTIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PITCH_TEXT = (
    "We have 500K active users on our platform and are growing 20% month-over-month. "
    "Our team of 3 engineers has built the product from scratch in 18 months. "
    "The total addressable market is $5B. We are raising a $1M seed round."
)


def _profile_with_text(text: str) -> FounderProfile:
    return FounderProfile(
        name="Test Founder",
        company="TestCo",
        sector="SaaS",
        stage="seed",
        raw_sources=[text],
    )


def _traction_claim() -> Claim:
    return Claim(
        claim_text="We have 500K active users",
        category="traction",
        confidence_score=0.8,
        source_reference="pitch_deck",
    )


def _team_claim() -> Claim:
    return Claim(
        claim_text="a team of 3 engineers",
        category="team",
        confidence_score=0.8,
        source_reference="pitch_deck",
    )


def _cap_table_claim() -> Claim:
    return Claim(
        claim_text="not disclosed",
        category="other",
        confidence_score=1.0,
        source_reference="cap_table: not disclosed in profile data",
    )


def _low_star_evidence() -> list:
    return [{"signal": "star_growth", "score": 10, "direction": "bearish"}]


def _total_stars_evidence() -> list:
    return [{"signal": "total_stars", "score": 10, "direction": "bearish"}]


def _contributor_evidence(count: float = 3) -> list:
    return [{"signal": "contributor_count", "score": count, "direction": "neutral"}]


def _mock_ollama_response(claims_data: list):
    """Build a mock requests.post response that returns claims_data as JSON."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": json.dumps(claims_data)}
    }
    return mock_resp


# ---------------------------------------------------------------------------
# extract_claims — happy path (mocked Ollama)
# ---------------------------------------------------------------------------

def test_extract_claims_happy_path_returns_traction_claim():
    mock_data = [
        {
            "claim_text": "We have 500K active users",
            "category": "traction",
            "confidence_score": 0.85,
            "source_reference": "pitch_deck",
        }
    ]
    with patch("data.trust_score.requests.post", return_value=_mock_ollama_response(mock_data)):
        result = extract_claims(_profile_with_text(PITCH_TEXT))

    texts = [c.claim_text for c in result]
    assert any("500K" in t or "500k" in t.lower() for t in texts), (
        f"Expected a 500K traction claim. Got: {texts}"
    )


def test_extract_claims_happy_path_returns_claim_objects():
    mock_data = [
        {
            "claim_text": "TAM is $5B",
            "category": "market_size",
            "confidence_score": 0.7,
            "source_reference": "pitch_deck",
        }
    ]
    with patch("data.trust_score.requests.post", return_value=_mock_ollama_response(mock_data)):
        result = extract_claims(_profile_with_text(PITCH_TEXT))

    assert all(isinstance(c, Claim) for c in result)


def test_extract_claims_confidence_score_in_range():
    mock_data = [
        {
            "claim_text": "20% MoM growth",
            "category": "traction",
            "confidence_score": 0.9,
            "source_reference": "pitch_deck",
        }
    ]
    with patch("data.trust_score.requests.post", return_value=_mock_ollama_response(mock_data)):
        result = extract_claims(_profile_with_text(PITCH_TEXT))

    for c in result:
        assert 0.0 <= c.confidence_score <= 1.0


def test_extract_claims_category_is_valid():
    valid_categories = {"traction", "revenue", "team", "market_size", "other"}
    mock_data = [
        {"claim_text": "3 engineers", "category": "team", "confidence_score": 0.8, "source_reference": "deck"},
        {"claim_text": "Unknown category", "category": "invalid_cat", "confidence_score": 0.5, "source_reference": "deck"},
    ]
    with patch("data.trust_score.requests.post", return_value=_mock_ollama_response(mock_data)):
        result = extract_claims(_profile_with_text(PITCH_TEXT))

    for c in result:
        assert c.category in valid_categories, f"Invalid category: {c.category}"


# ---------------------------------------------------------------------------
# extract_claims — offline fallback
# ---------------------------------------------------------------------------

def test_extract_claims_offline_fallback_does_not_raise():
    with patch("data.trust_score.requests.post", side_effect=ConnectionError("Ollama not running")):
        result = extract_claims(_profile_with_text(PITCH_TEXT))
    assert isinstance(result, list)


def test_extract_claims_offline_fallback_returns_gap_claims():
    with patch("data.trust_score.requests.post", side_effect=ConnectionError("Ollama not running")):
        result = extract_claims(_profile_with_text(PITCH_TEXT))
    assert len(result) >= 1
    not_disclosed_claims = [c for c in result if c.claim_text == "not disclosed"]
    assert len(not_disclosed_claims) >= 1, "Offline fallback must return at least one 'not disclosed' gap claim"


def test_extract_claims_no_text_in_raw_sources_returns_gap_claims():
    profile = FounderProfile(
        name="Test",
        company="X",
        raw_sources=["https://github.com/test"],  # URL — not text content
    )
    with patch("data.trust_score.requests.post") as mock_post:
        result = extract_claims(profile)
    # URL-only profile should not call Ollama and should return gap claims
    assert any(c.claim_text == "not disclosed" for c in result)


# ---------------------------------------------------------------------------
# extract_claims — gap flagging
# ---------------------------------------------------------------------------

def test_extract_claims_revenue_absent_returns_not_disclosed_claim():
    profile = FounderProfile(
        name="Test",
        company="TestCo",
        key_signals={},
        raw_sources=[],
    )
    with patch("data.trust_score.requests.post", side_effect=ConnectionError):
        result = extract_claims(profile)
    revenue_gap = [
        c for c in result
        if c.claim_text == "not disclosed" and "revenue" in c.source_reference
    ]
    assert len(revenue_gap) >= 1, f"Expected revenue gap claim. Got: {[c.source_reference for c in result]}"


def test_extract_claims_gap_claims_have_confidence_1():
    profile = FounderProfile(name="X", company="Y", key_signals={}, raw_sources=[])
    with patch("data.trust_score.requests.post", side_effect=ConnectionError):
        result = extract_claims(profile)
    for c in result:
        if c.claim_text == "not disclosed":
            assert c.confidence_score == 1.0


def test_extract_claims_all_gap_sections_flagged_on_empty_profile():
    profile = FounderProfile(name="X", company="Y", key_signals={}, raw_sources=[])
    with patch("data.trust_score.requests.post", side_effect=ConnectionError):
        result = extract_claims(profile)
    sources = [c.source_reference for c in result if c.claim_text == "not disclosed"]
    for section in _GAP_SECTIONS:
        assert any(section in s for s in sources), f"Expected gap claim for section: {section}"


# ---------------------------------------------------------------------------
# verify_claim — contradicted
# ---------------------------------------------------------------------------

def test_verify_claim_contradicted_high_user_count_low_star_signal():
    result = verify_claim(_traction_claim(), _low_star_evidence())
    assert result.status == "contradicted"
    assert result.contradiction_note
    assert len(result.contradiction_note) > 0


def test_verify_claim_contradicted_works_with_total_stars_key():
    result = verify_claim(_traction_claim(), _total_stars_evidence())
    assert result.status == "contradicted"


def test_verify_claim_contradicted_verification_confidence_high():
    result = verify_claim(_traction_claim(), _low_star_evidence())
    assert result.verification_confidence >= 0.8


def test_verify_claim_contradicted_returns_verified_claim_object():
    result = verify_claim(_traction_claim(), _low_star_evidence())
    assert isinstance(result, VerifiedClaim)
    assert result.claim is _traction_claim() or result.claim.claim_text == _traction_claim().claim_text


# ---------------------------------------------------------------------------
# verify_claim — unverifiable
# ---------------------------------------------------------------------------

def test_verify_claim_cap_table_no_evidence_is_unverifiable():
    result = verify_claim(_cap_table_claim(), [])
    assert result.status == "unverifiable"
    assert isinstance(result, VerifiedClaim)


def test_verify_claim_unverifiable_claim_not_dropped():
    result = verify_claim(_cap_table_claim(), [])
    assert result is not None


def test_verify_claim_revenue_claim_no_signal_is_unverifiable():
    revenue_claim = Claim(
        claim_text="$500K ARR last quarter",
        category="revenue",
        confidence_score=0.7,
        source_reference="pitch_deck",
    )
    result = verify_claim(revenue_claim, [])
    assert result.status == "unverifiable"


def test_verify_claim_market_size_no_signal_is_unverifiable():
    ms_claim = Claim(
        claim_text="Total addressable market is $10B",
        category="market_size",
        confidence_score=0.6,
        source_reference="pitch_deck",
    )
    result = verify_claim(ms_claim, [])
    assert result.status == "unverifiable"


# ---------------------------------------------------------------------------
# verify_claim — verified
# ---------------------------------------------------------------------------

def test_verify_claim_team_claim_matches_contributor_count():
    result = verify_claim(_team_claim(), _contributor_evidence(3))
    assert result.status == "verified"


def test_verify_claim_team_verified_has_supporting_evidence():
    result = verify_claim(_team_claim(), _contributor_evidence(3))
    assert len(result.supporting_evidence) >= 1
    assert any("contributor_count" in e for e in result.supporting_evidence)


def test_verify_claim_team_verified_confidence_at_least_0_7():
    result = verify_claim(_team_claim(), _contributor_evidence(3))
    assert result.verification_confidence >= 0.7


def test_verify_claim_team_size_off_by_one_still_verified():
    claim = Claim(
        claim_text="team of 4 engineers",
        category="team",
        confidence_score=0.8,
        source_reference="deck",
    )
    result = verify_claim(claim, _contributor_evidence(3))
    assert result.status == "verified"


# ---------------------------------------------------------------------------
# verify_claim — not-disclosed claims
# ---------------------------------------------------------------------------

def test_verify_not_disclosed_claim_is_always_unverifiable():
    result = verify_claim(_cap_table_claim(), _low_star_evidence())
    assert result.status == "unverifiable"


def test_verify_not_disclosed_claim_verification_confidence_is_1():
    result = verify_claim(_cap_table_claim(), [])
    assert result.verification_confidence == 1.0


def test_verify_not_disclosed_claim_never_returns_none():
    result = verify_claim(_cap_table_claim(), [])
    assert result is not None


# ---------------------------------------------------------------------------
# verify_claim — never raises
# ---------------------------------------------------------------------------

def test_verify_claim_never_raises_on_empty_evidence():
    for cat in ("traction", "revenue", "team", "market_size", "other"):
        c = Claim(claim_text="some claim", category=cat, confidence_score=0.5, source_reference="test")
        result = verify_claim(c, [])
        assert isinstance(result, VerifiedClaim)


def test_verify_claim_never_raises_on_malformed_evidence():
    result = verify_claim(
        _traction_claim(),
        [{"broken": True}, None, 42, {"signal": "star_growth"}],  # malformed entries
    )
    assert isinstance(result, VerifiedClaim)
