"""Tests for data/founder_signals.py — no network calls."""
from data.founder_data import FounderProfile
from data.founder_signals import generate_founder_signals


def _make_profile(**key_signals) -> FounderProfile:
    return FounderProfile(key_signals=key_signals)


def test_no_github_data_all_signals_unknown():
    profile = _make_profile()
    result = generate_founder_signals(profile)
    for name in ("commit_frequency", "star_growth", "contributor_count", "recency", "tech_stack_depth"):
        assert result[name]["score"] is None
        assert result[name]["direction"] == "unknown"


def test_stale_repo_recency_bearish():
    profile = _make_profile(recency=200)
    result = generate_founder_signals(profile)
    assert result["recency"]["direction"] == "bearish"


def test_recent_repo_recency_bullish():
    profile = _make_profile(recency=3)
    result = generate_founder_signals(profile)
    assert result["recency"]["direction"] == "bullish"


def test_solo_founder_contributor_count_bearish():
    profile = _make_profile(contributor_count=1)
    result = generate_founder_signals(profile)
    assert result["contributor_count"]["direction"] == "bearish"
    assert result["contributor_count"]["score"] < 30


def test_high_star_growth_bullish():
    profile = _make_profile(star_growth=600)
    result = generate_founder_signals(profile)
    assert result["star_growth"]["direction"] == "bullish"
    assert result["star_growth"]["score"] >= 90


def test_active_commits_bullish():
    profile = _make_profile(commit_frequency=12)
    result = generate_founder_signals(profile)
    assert result["commit_frequency"]["direction"] == "bullish"


def test_zero_commits_bearish():
    profile = _make_profile(commit_frequency=0)
    result = generate_founder_signals(profile)
    assert result["commit_frequency"]["direction"] == "bearish"


def test_all_five_signals_present_in_output():
    profile = _make_profile(
        commit_frequency=8, star_growth=150, contributor_count=5,
        recency=14, tech_stack_depth=4,
    )
    result = generate_founder_signals(profile)
    assert set(result.keys()) == {
        "commit_frequency", "star_growth", "contributor_count", "recency", "tech_stack_depth"
    }
    for v in result.values():
        assert "score" in v and "direction" in v


def test_never_raises_on_none_profile():
    profile = FounderProfile()
    result = generate_founder_signals(profile)
    assert isinstance(result, dict)
