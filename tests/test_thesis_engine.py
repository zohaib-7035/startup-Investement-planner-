"""Tests for data/thesis_engine.py."""
from data.founder_data import FounderProfile
from data.thesis_engine import ThesisConfig, ThesisResult, evaluate_founder


def _profile(**kwargs) -> FounderProfile:
    return FounderProfile(**kwargs)


def test_sector_mismatch_returns_fail_with_named_rule():
    config = ThesisConfig(sectors=["FinTech"])
    profile = _profile(sector="HealthTech")
    result = evaluate_founder(profile, config)
    assert result.verdict == "FAIL"
    assert "sector_match" in result.failed_rules


def test_sector_match_returns_pass_with_named_rule():
    config = ThesisConfig(sectors=["FinTech"])
    profile = _profile(sector="FinTech")
    result = evaluate_founder(profile, config)
    assert result.verdict == "PASS"
    assert "sector_match" in result.matched_rules


def test_stage_mismatch_returns_fail():
    config = ThesisConfig(stages=["Series A"])
    profile = _profile(stage="seed")
    result = evaluate_founder(profile, config)
    assert result.verdict == "FAIL"
    assert "stage_match" in result.failed_rules


def test_all_criteria_match_returns_pass():
    config = ThesisConfig(sectors=["SaaS"], stages=["Series A"])
    profile = _profile(sector="SaaS", stage="Series A")
    result = evaluate_founder(profile, config)
    assert result.verdict == "PASS"
    assert len(result.matched_rules) >= 2
    assert len(result.failed_rules) == 0


def test_no_constraints_returns_watchlist():
    config = ThesisConfig()
    profile = _profile()
    result = evaluate_founder(profile, config)
    assert result.verdict == "WATCHLIST"


def test_low_risk_appetite_rejects_solo_founder():
    config = ThesisConfig(risk_appetite="low")
    profile = _profile(key_signals={"contributor_count": 1})
    result = evaluate_founder(profile, config)
    assert result.verdict == "FAIL"
    assert "risk_appetite_match" in result.failed_rules


def test_score_is_ratio_of_matched_to_total():
    config = ThesisConfig(sectors=["FinTech"], stages=["Series A"])
    profile = _profile(sector="FinTech", stage="seed")
    result = evaluate_founder(profile, config)
    assert isinstance(result.score, float)
    assert 0.0 <= result.score <= 1.0


def test_result_is_always_thesis_result_type():
    result = evaluate_founder(FounderProfile(), ThesisConfig())
    assert isinstance(result, ThesisResult)
