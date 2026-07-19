"""Tests for data/risk_flags.py."""
from data.founder_data import FounderProfile
from data.risk_flags import RiskFlag, flag_risks


def _signals(**overrides) -> dict:
    base = {
        "commit_frequency":  {"score": 70, "direction": "bullish"},
        "star_growth":       {"score": 60, "direction": "bullish"},
        "contributor_count": {"score": 60, "direction": "neutral"},
        "recency":           {"score": 75, "direction": "bullish"},
        "tech_stack_depth":  {"score": 65, "direction": "neutral"},
    }
    base.update(overrides)
    return base


# ── solo_founder ──────────────────────────────────────────────────────────────

def test_solo_founder_key_signal_triggers_medium_flag():
    profile = FounderProfile(key_signals={"contributor_count": 1})
    signals = _signals(contributor_count={"score": 15, "direction": "bearish"})
    flags = flag_risks(profile, signals)
    solo = [f for f in flags if f.category == "solo_founder"]
    assert len(solo) == 1
    assert solo[0].severity == "medium"


def test_team_founder_no_solo_flag():
    profile = FounderProfile(key_signals={"contributor_count": 5})
    signals = _signals(contributor_count={"score": 60, "direction": "neutral"})
    flags = flag_risks(profile, signals)
    assert not any(f.category == "solo_founder" for f in flags)


# ── stale_repo ────────────────────────────────────────────────────────────────

def test_stale_repo_bearish_recency_triggers_flag():
    profile = FounderProfile(key_signals={"recency": 200})
    signals = _signals(recency={"score": 10, "direction": "bearish"})
    flags = flag_risks(profile, signals)
    stale = [f for f in flags if f.category == "stale_repo"]
    assert len(stale) == 1


# ── missing_data ──────────────────────────────────────────────────────────────

def test_unknown_signals_generate_low_severity_flags():
    profile = FounderProfile()
    signals = {k: {"score": None, "direction": "unknown"} for k in
               ("commit_frequency", "star_growth", "contributor_count", "recency", "tech_stack_depth")}
    flags = flag_risks(profile, signals)
    missing = [f for f in flags if f.category == "missing_data"]
    assert len(missing) == 5
    assert all(f.severity == "low" for f in missing)


def test_fully_populated_signals_no_missing_data_flags():
    profile = FounderProfile(key_signals={"contributor_count": 3})
    flags = flag_risks(profile, _signals())
    assert not any(f.category == "missing_data" for f in flags)


# ── claim_contradiction ───────────────────────────────────────────────────────

def test_large_user_claim_with_low_star_score_triggers_high_flag():
    profile = FounderProfile(key_signals={"claimed_users": 500_000})
    signals = _signals(star_growth={"score": 10, "direction": "bearish"})
    flags = flag_risks(profile, signals)
    contradictions = [f for f in flags if f.category == "claim_contradiction"]
    assert len(contradictions) == 1
    assert contradictions[0].severity == "high"


def test_large_user_claim_with_high_star_score_no_contradiction():
    profile = FounderProfile(key_signals={"claimed_users": 500_000})
    signals = _signals(star_growth={"score": 80, "direction": "bullish"})
    flags = flag_risks(profile, signals)
    assert not any(f.category == "claim_contradiction" for f in flags)


# ── general ───────────────────────────────────────────────────────────────────

def test_clean_profile_no_flags():
    profile = FounderProfile(key_signals={"contributor_count": 5, "claimed_users": 100})
    flags = flag_risks(profile, _signals())
    assert flags == []


def test_result_is_always_list():
    result = flag_risks(FounderProfile(), {})
    assert isinstance(result, list)


def test_flag_dataclass_has_required_fields():
    profile = FounderProfile(key_signals={"contributor_count": 1})
    signals = _signals(contributor_count={"score": 10, "direction": "bearish"})
    flags = flag_risks(profile, signals)
    for f in flags:
        assert isinstance(f, RiskFlag)
        assert f.category
        assert f.description
        assert f.severity in ("low", "medium", "high")
