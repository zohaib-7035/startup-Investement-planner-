"""Tests for data/memo_generator.py."""
from data.founder_data import FounderProfile
from data.decision_engine import DecisionResult, AxisScore
from data.memo_generator import NOT_DISCLOSED, InvestmentMemo, generate_memo


def _minimal_profile() -> FounderProfile:
    return FounderProfile(company="Acme", sector="SaaS", stage="Series A")


def _minimal_decision() -> DecisionResult:
    return DecisionResult(
        axes=[AxisScore("Founder", 0.7, "stable", "test")],
        overall_verdict="PASS",
    )


# ── Sentinel constant ─────────────────────────────────────────────────────────

def test_not_disclosed_sentinel_exact_value():
    assert NOT_DISCLOSED == "[Not Disclosed]"


# ── Required sections always present ─────────────────────────────────────────

def test_required_sections_always_present_on_minimal_input():
    memo = generate_memo(FounderProfile())
    assert memo.company_snapshot
    assert memo.investment_hypotheses
    assert memo.swot
    assert memo.problem_and_product
    assert memo.traction_and_kpis


def test_required_sections_are_strings():
    memo = generate_memo(_minimal_profile())
    for field in ("company_snapshot", "investment_hypotheses", "swot", "problem_and_product", "traction_and_kpis"):
        assert isinstance(getattr(memo, field), str)


# ── Optional sections default to NOT_DISCLOSED ────────────────────────────────

def test_cap_table_absent_returns_not_disclosed():
    memo = generate_memo(_minimal_profile(), decision=_minimal_decision())
    assert memo.cap_table == NOT_DISCLOSED


def test_financials_absent_returns_not_disclosed():
    memo = generate_memo(_minimal_profile())
    assert memo.financials == NOT_DISCLOSED


def test_team_bios_absent_returns_not_disclosed():
    memo = generate_memo(_minimal_profile())
    assert memo.team_bios == NOT_DISCLOSED


def test_optional_section_not_empty_string_or_none():
    memo = generate_memo(FounderProfile())
    assert memo.cap_table not in (None, "")
    assert memo.financials not in (None, "")
    assert memo.team_bios not in (None, "")


# ── Optional sections populated when data is present ─────────────────────────

def test_financials_populated_when_present_in_memo_inputs():
    decision = DecisionResult(
        axes=[],
        overall_verdict="PASS",
        memo_inputs={"financials": "$2M ARR, 3x YoY growth"},
    )
    memo = generate_memo(_minimal_profile(), decision=decision)
    assert memo.financials != NOT_DISCLOSED
    assert "ARR" in memo.financials


# ── General ───────────────────────────────────────────────────────────────────

def test_result_is_always_investment_memo_type():
    result = generate_memo(FounderProfile())
    assert isinstance(result, InvestmentMemo)


def test_never_raises_on_none_inputs():
    memo = generate_memo(FounderProfile(), thesis_result=None, risk_flags=None, decision=None)
    assert isinstance(memo, InvestmentMemo)


def test_company_name_appears_in_snapshot():
    profile = FounderProfile(company="DeepThought AI")
    memo = generate_memo(profile)
    assert "DeepThought AI" in memo.company_snapshot


def test_high_risk_flag_appears_in_swot():
    from data.risk_flags import RiskFlag
    flags = [RiskFlag(category="claim_contradiction", description="User claim unverified.", severity="high")]
    memo = generate_memo(_minimal_profile(), risk_flags=flags)
    assert "claim_contradiction" in memo.swot
