"""
Tests for data/scoring_engine.py.
All Ollama calls mocked — no live network required to pass CI.
FounderMemory file I/O redirected via monkeypatch on _MEMORY_PATH.
"""
import dataclasses
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data.founder_data import FounderProfile
from data.thesis_engine import ThesisConfig
import data.scoring_engine as se
from data.scoring_engine import (
    FounderMemory,
    FounderQueryOutput,
    IdeaVsMarketOutput,
    ScreeningResult,
    query_founders,
    run_full_screening,
    score_founder_axis,
    score_idea_vs_market_axis,
    score_market_axis,
)
from data.decision_engine import AxisScore


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def memory_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect FounderMemory to a temp file so tests don't touch real founder_memory.json."""
    p = tmp_path / "founder_memory.json"
    monkeypatch.setattr(se, "_MEMORY_PATH", p)
    return p


def _profile(**kwargs) -> FounderProfile:
    defaults = dict(
        name="Ada Lovelace",
        company="NeuralCo",
        sector="AI/ML",
        stage="pre-seed",
        github_url="https://github.com/ada",
        key_signals={
            "commit_frequency": 12,
            "star_growth": 600,
            "contributor_count": 3,
            "recency": 5,
            "tech_stack_depth": 4,
        },
    )
    defaults.update(kwargs)
    return FounderProfile(**defaults)


def _screening_result(company="TestCo", sector="AI/ML") -> ScreeningResult:
    profile = _profile(company=company, sector=sector)
    return ScreeningResult(
        profile=profile,
        founder_axis=AxisScore("founder", 75, "stable", "test", ["sig=75 → bullish"]),
        market_axis=AxisScore("market", 80, "stable", "test", ["sector=AI/ML → bullish"]),
        idea_vs_market_axis=AxisScore("idea_vs_market", 70, "stable", "test", ["good fit"]),
    )


# ── FounderMemory tests ───────────────────────────────────────────────────────

def test_founder_memory_load_returns_empty_dict_when_file_missing(memory_path: Path):
    assert not memory_path.exists()
    mem = FounderMemory(path=memory_path)
    assert mem.load() == {}


def test_founder_memory_load_returns_empty_dict_on_corrupt_json(memory_path: Path):
    memory_path.write_text("NOT VALID JSON", encoding="utf-8")
    mem = FounderMemory(path=memory_path)
    assert mem.load() == {}


def test_founder_memory_update_persists_score_and_history_grows(memory_path: Path):
    mem = FounderMemory(path=memory_path)
    mem.update("ada", 70.0)
    mem.update("ada", 85.0)
    history = mem.history("ada")
    assert history == [70.0, 85.0]


def test_founder_memory_history_returns_empty_list_for_unknown_identity(memory_path: Path):
    mem = FounderMemory(path=memory_path)
    assert mem.history("unknown::founder") == []


def test_founder_memory_identity_prefers_github_url(memory_path: Path):
    mem = FounderMemory(path=memory_path)
    profile = _profile(github_url="https://github.com/ada")
    identity = mem._identity(profile)
    assert identity == "https://github.com/ada"


def test_founder_memory_identity_falls_back_to_name_company(memory_path: Path):
    mem = FounderMemory(path=memory_path)
    profile = _profile(github_url=None, name="Ada Lovelace", company="NeuralCo")
    identity = mem._identity(profile)
    assert identity == "ada lovelace::neuralco"


# ── score_founder_axis tests ─────────────────────────────────────────────────

def test_score_founder_axis_score_in_range_and_evidence_non_empty(memory_path: Path):
    profile = _profile()
    result = score_founder_axis(profile)
    assert 0 <= result.score <= 100
    assert len(result.evidence) >= 3
    assert all(isinstance(e, str) for e in result.evidence)


def test_score_founder_axis_evidence_names_signals(memory_path: Path):
    profile = _profile()
    result = score_founder_axis(profile)
    combined = " ".join(result.evidence)
    for signal_name in ("commit_frequency", "star_growth", "contributor_count"):
        assert signal_name in combined, f"Expected '{signal_name}' in evidence but got: {result.evidence}"


def test_score_founder_axis_new_founder_trend_is_stable(memory_path: Path):
    profile = _profile()
    result = score_founder_axis(profile)
    assert result.trend == "stable"


def test_score_founder_axis_second_call_improving_trend(memory_path: Path):
    profile_low = _profile(key_signals={
        "commit_frequency": 0,
        "star_growth": 0,
        "contributor_count": 1,
        "recency": 200,
        "tech_stack_depth": 1,
    })
    profile_high = _profile(key_signals={
        "commit_frequency": 20,
        "star_growth": 2000,
        "contributor_count": 10,
        "recency": 2,
        "tech_stack_depth": 8,
    })
    r1 = score_founder_axis(profile_low)
    r2 = score_founder_axis(profile_high)
    assert r2.trend == "improving"
    assert r1.score < r2.score


def test_score_founder_axis_declining_trend_when_score_drops(memory_path: Path):
    profile_high = _profile(key_signals={
        "commit_frequency": 20,
        "star_growth": 2000,
        "contributor_count": 10,
        "recency": 2,
        "tech_stack_depth": 8,
    })
    profile_low = _profile(key_signals={
        "commit_frequency": 0,
        "star_growth": 0,
        "contributor_count": 1,
        "recency": 200,
        "tech_stack_depth": 1,
    })
    score_founder_axis(profile_high)
    r2 = score_founder_axis(profile_low)
    assert r2.trend == "declining"


def test_score_founder_axis_no_signals_fallback_score_50(memory_path: Path):
    profile = _profile(
        github_url=None,
        key_signals={},
    )
    result = score_founder_axis(profile)
    assert result.score == 50.0
    assert any("no GitHub signals" in e for e in result.evidence)


def test_score_founder_axis_score_written_to_store(memory_path: Path):
    profile = _profile()
    result = score_founder_axis(profile)
    mem = FounderMemory(path=memory_path)
    history = mem.history(profile.github_url)
    assert len(history) == 1
    assert history[0] == result.score
    assert 0 <= history[0] <= 100


# ── score_market_axis tests ───────────────────────────────────────────────────

def test_score_market_axis_bullish_sector_score_at_least_80():
    profile = _profile(sector="AI/ML", stage="pre-seed")
    result = score_market_axis(profile)
    assert result.score >= 80
    combined = " ".join(result.evidence)
    assert "AI/ML" in combined
    assert "bullish" in combined


def test_score_market_axis_pre_seed_bonus_applied():
    profile_seed = _profile(sector="AI/ML", stage="pre-seed")
    profile_series_a = _profile(sector="AI/ML", stage="Series A")
    r_seed = score_market_axis(profile_seed)
    r_a = score_market_axis(profile_series_a)
    assert r_seed.score > r_a.score


def test_score_market_axis_other_sector_score_at_most_30():
    profile = _profile(sector="Other", stage="Series A")
    result = score_market_axis(profile)
    assert result.score <= 30


def test_score_market_axis_unknown_sector_falls_back_to_bear():
    profile = _profile(sector="QuantumBio", stage="seed")
    result = score_market_axis(profile)
    assert result.score <= 35


def test_score_market_axis_trend_always_stable():
    for sector in ("AI/ML", "FinTech", "HealthTech", "SaaS", "Other"):
        profile = _profile(sector=sector)
        result = score_market_axis(profile)
        assert result.trend == "stable", f"Expected stable trend for {sector}"


def test_score_market_axis_evidence_references_sector_and_stage():
    profile = _profile(sector="AI/ML", stage="pre-seed")
    result = score_market_axis(profile)
    combined = " ".join(result.evidence)
    assert "AI/ML" in combined
    assert "pre-seed" in combined


# ── score_idea_vs_market_axis tests ──────────────────────────────────────────

@patch("data.scoring_engine.requests.post")
def test_score_idea_vs_market_axis_happy_path(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "fit_score": 80,
                "pivot_potential": 70,
                "combined_score": 76,
                "rationale": "Strong AI/ML idea in a bullish market",
                "evidence": ["AI fit confirmed", "team can pivot", "market timing good"],
            })
        }
    }
    mock_post.return_value = mock_resp

    profile = _profile()
    result = score_idea_vs_market_axis(profile)
    assert result.name == "idea_vs_market"
    assert result.score == 76.0
    assert result.rationale == "Strong AI/ML idea in a bullish market"
    assert result.evidence == ["AI fit confirmed", "team can pivot", "market timing good"]


@patch("data.scoring_engine.requests.post", side_effect=ConnectionError("no ollama"))
def test_score_idea_vs_market_axis_offline_fallback(mock_post):
    profile = _profile()
    result = score_idea_vs_market_axis(profile)
    assert result.score == 50.0
    assert result.trend == "stable"
    assert any("LLM unavailable" in e for e in result.evidence)


@patch("data.scoring_engine.requests.post")
def test_score_idea_vs_market_axis_malformed_json_returns_fallback(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "not valid json at all"}}
    mock_post.return_value = mock_resp

    profile = _profile()
    result = score_idea_vs_market_axis(profile)
    assert result.score == 50.0
    assert any("LLM unavailable" in e for e in result.evidence)


# ── run_full_screening tests ──────────────────────────────────────────────────

@patch("data.scoring_engine.requests.post")
def test_run_full_screening_returns_all_three_axes(mock_post, memory_path: Path):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "fit_score": 70, "pivot_potential": 65, "combined_score": 68,
                "rationale": "good fit", "evidence": ["e1", "e2", "e3"],
            })
        }
    }
    mock_post.return_value = mock_resp

    profile = _profile()
    result = run_full_screening(profile)
    assert isinstance(result, ScreeningResult)
    assert result.founder_axis is not None
    assert result.market_axis is not None
    assert result.idea_vs_market_axis is not None
    assert isinstance(result.risk_flags, list)


def test_screening_result_has_no_combined_score_field():
    field_names = {f.name for f in dataclasses.fields(ScreeningResult)}
    forbidden = {"combined_score", "total_score", "average_score", "weighted_score"}
    overlap = field_names & forbidden
    assert not overlap, f"ScreeningResult must not have combining fields: {overlap}"


@patch("data.scoring_engine.requests.post", side_effect=ConnectionError)
def test_run_full_screening_thesis_mismatch(mock_post, memory_path: Path):
    profile = _profile(sector="HealthTech")
    config = ThesisConfig(sectors=["FinTech"])
    result = run_full_screening(profile, thesis_config=config)
    assert result.thesis_match is False
    assert "sector_match" in result.thesis_reason


@patch("data.scoring_engine.score_founder_axis")
@patch("data.scoring_engine.score_market_axis")
@patch("data.scoring_engine.score_idea_vs_market_axis")
def test_run_full_screening_parallel_under_half_second(
    mock_idea, mock_market, mock_founder, memory_path: Path
):
    def _slow_axis(profile):
        time.sleep(0.1)
        return AxisScore("test", 75, "stable", "ok", ["x"])

    mock_founder.side_effect = _slow_axis
    mock_market.side_effect = _slow_axis
    mock_idea.side_effect = _slow_axis

    profile = _profile()
    start = time.time()
    run_full_screening(profile)
    elapsed = time.time() - start
    assert elapsed < 0.5, f"run_full_screening took {elapsed:.2f}s — axes should run in parallel"


@patch("data.scoring_engine.requests.post", side_effect=ConnectionError)
def test_run_full_screening_risk_flags_detect_solo_founder(mock_post, memory_path: Path):
    profile = _profile(key_signals={"contributor_count": 1, "claimed_users": 600_000})
    result = run_full_screening(profile)
    assert isinstance(result.risk_flags, list)
    categories = [f.category for f in result.risk_flags]
    assert "solo_founder" in categories, f"Expected solo_founder flag but got: {categories}"
    solo_flag = next(f for f in result.risk_flags if f.category == "solo_founder")
    assert solo_flag.severity in ("medium", "high")


# ── query_founders tests ──────────────────────────────────────────────────────

def test_query_founders_empty_list_returns_empty_without_llm_call():
    with patch("data.scoring_engine.requests.post") as mock_post:
        result = query_founders("AI infra", [])
    mock_post.assert_not_called()
    assert result == []


@patch("data.scoring_engine.requests.post")
def test_query_founders_index_filter_returns_correct_profiles(mock_post):
    profiles = [_screening_result(company=f"Co{i}") for i in range(5)]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({"matched_indices": [1, 3], "reasoning": "best match"})
        }
    }
    mock_post.return_value = mock_resp

    result = query_founders("AI infra enterprise traction", profiles)
    assert len(result) == 2
    assert result[0].profile.company == "Co1"
    assert result[1].profile.company == "Co3"


@patch("data.scoring_engine.requests.post", side_effect=ConnectionError("no ollama"))
def test_query_founders_offline_fallback_returns_all_profiles(mock_post):
    profiles = [_screening_result(company=f"Co{i}") for i in range(5)]
    result = query_founders("AI infra", profiles)
    assert result == profiles


@patch("data.scoring_engine.requests.post")
def test_query_founders_out_of_range_index_silently_dropped(mock_post):
    profiles = [_screening_result(company=f"Co{i}") for i in range(5)]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({"matched_indices": [0, 99], "reasoning": "test"})
        }
    }
    mock_post.return_value = mock_resp

    result = query_founders("test", profiles)
    assert len(result) == 1
    assert result[0].profile.company == "Co0"


@patch("data.scoring_engine.requests.post")
def test_query_founders_result_elements_are_screening_results(mock_post):
    profiles = [_screening_result(company=f"Co{i}") for i in range(3)]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({"matched_indices": [0, 2], "reasoning": "ok"})
        }
    }
    mock_post.return_value = mock_resp

    result = query_founders("test query", profiles)
    assert all(isinstance(r, ScreeningResult) for r in result)


@patch("data.scoring_engine.requests.post")
def test_query_founders_malformed_llm_response_returns_all(mock_post):
    profiles = [_screening_result(company=f"Co{i}") for i in range(3)]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "not json"}}
    mock_post.return_value = mock_resp
    result = query_founders("test", profiles)
    assert result == profiles
