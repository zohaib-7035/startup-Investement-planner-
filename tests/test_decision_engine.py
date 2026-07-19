"""Tests for data/decision_engine.py — enforces axis independence."""
from data.decision_engine import AxisScore, DecisionResult, make_decision


def _axis(name="Founder", score=50, trend="stable") -> AxisScore:
    return AxisScore(name=name, score=score, trend=trend, rationale="test")


def test_decision_result_has_no_top_level_score_field():
    result = make_decision(_axis(), _axis("Market"), _axis("Idea-vs-Market"))
    assert not hasattr(result, "score"), (
        "DecisionResult must not have a top-level 'score' field — axes are never averaged"
    )


def test_all_three_axes_preserved_independently():
    fa = _axis("Founder", score=80, trend="improving")
    ma = _axis("Market", score=30, trend="declining")
    ia = _axis("Idea-vs-Market", score=60, trend="stable")
    result = make_decision(fa, ma, ia)
    assert len(result.axes) == 3
    names = {a.name for a in result.axes}
    assert names == {"Founder", "Market", "Idea-vs-Market"}


def test_each_axis_retains_its_own_trend():
    fa = _axis("Founder", trend="improving")
    ma = _axis("Market", trend="declining")
    ia = _axis("Idea-vs-Market", trend="stable")
    result = make_decision(fa, ma, ia)
    trends = {a.name: a.trend for a in result.axes}
    assert trends["Founder"] == "improving"
    assert trends["Market"] == "declining"
    assert trends["Idea-vs-Market"] == "stable"


def test_each_axis_retains_its_own_score():
    fa = _axis("Founder", score=90)
    ma = _axis("Market", score=10)
    ia = _axis("Idea-vs-Market", score=50)
    result = make_decision(fa, ma, ia)
    scores = {a.name: a.score for a in result.axes}
    assert scores["Founder"] == 90
    assert scores["Market"] == 10
    assert scores["Idea-vs-Market"] == 50


def test_overall_verdict_pass_when_all_axes_high():
    result = make_decision(
        _axis("Founder", score=80),
        _axis("Market", score=90),
        _axis("Idea-vs-Market", score=70),
    )
    assert result.overall_verdict == "PASS"


def test_overall_verdict_fail_when_all_axes_low():
    result = make_decision(
        _axis("Founder", score=10),
        _axis("Market", score=20),
        _axis("Idea-vs-Market", score=30),
    )
    assert result.overall_verdict == "FAIL"


def test_thesis_result_verdict_takes_priority():
    class _FakeThesis:
        verdict = "FAIL"
        matched_rules = []
        failed_rules = ["sector_match"]

    result = make_decision(
        _axis("Founder", score=90),
        _axis("Market", score=90),
        _axis("Idea-vs-Market", score=90),
        thesis_result=_FakeThesis(),
    )
    assert result.overall_verdict == "FAIL"


def test_result_is_always_decision_result_type():
    result = make_decision(None, None, None)
    assert isinstance(result, DecisionResult)


def test_memo_inputs_contains_risk_flag_count():
    class _Flag:
        category = "solo_founder"
        severity = "medium"

    result = make_decision(_axis(), _axis("Market"), _axis("Idea-vs-Market"), risk_flags=[_Flag()])
    assert result.memo_inputs.get("total_risk_flags") == 1
