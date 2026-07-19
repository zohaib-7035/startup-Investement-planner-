"""Tests for data/founder_data.py — all GitHub HTTP calls are mocked."""
from unittest.mock import MagicMock, patch
from data.founder_data import FounderProfile, fetch_github_profile, ingest_pitch_deck


# ── fetch_github_profile ──────────────────────────────────────────────────────

def _mock_get(url, **kwargs):
    """Return canned responses keyed by URL fragment."""
    resp = MagicMock()
    if "/users/" in url and "/repos" not in url and "/contributors" not in url and "/stats" not in url:
        resp.status_code = 200
        resp.json.return_value = {"name": "Ada Lovelace", "company": "Acme Inc"}
    elif "/repos" in url and "sort=stars" in url:
        resp.status_code = 200
        resp.json.return_value = [
            {"name": "awesome-repo", "stargazers_count": 200, "language": "Python",
             "pushed_at": "2026-07-10T12:00:00Z"},
            {"name": "other-repo", "stargazers_count": 50, "language": "TypeScript",
             "pushed_at": "2026-06-01T08:00:00Z"},
        ]
    elif "/contributors" in url:
        resp.status_code = 200
        resp.json.return_value = [{"login": "user1"}, {"login": "user2"}, {"login": "user3"}]
    elif "/stats/commit_activity" in url:
        resp.status_code = 200
        resp.json.return_value = [{"total": 5}] * 12
    else:
        resp.status_code = 404
        resp.json.return_value = {}
    return resp


@patch("data.founder_data.requests.get", side_effect=_mock_get)
def test_happy_path_returns_profile_with_github_url(mock_get):
    profile = fetch_github_profile("ada")
    assert isinstance(profile, FounderProfile)
    assert profile.github_url == "https://github.com/ada"
    assert profile.name == "Ada Lovelace"


@patch("data.founder_data.requests.get", side_effect=_mock_get)
def test_happy_path_star_growth_populated(mock_get):
    profile = fetch_github_profile("ada")
    assert profile.key_signals.get("star_growth") is not None
    assert profile.key_signals["star_growth"] > 0


@patch("data.founder_data.requests.get", side_effect=_mock_get)
def test_happy_path_contributor_count_populated(mock_get):
    profile = fetch_github_profile("ada")
    assert profile.key_signals.get("contributor_count") == 3


def _mock_rate_limited(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 429
    resp.json.return_value = {}
    return resp


@patch("data.founder_data.requests.get", side_effect=_mock_rate_limited)
def test_rate_limit_returns_profile_with_warning_in_raw_sources(mock_get):
    profile = fetch_github_profile("ada")
    assert isinstance(profile, FounderProfile)
    assert any("rate-limited" in s for s in profile.raw_sources)
    assert profile.key_signals == {}


# ── ingest_pitch_deck ─────────────────────────────────────────────────────────

def test_series_a_fintech_deck_sets_stage_and_sector():
    text = "We are raising a Series A round for our FinTech startup focused on payment innovation."
    profile = ingest_pitch_deck(text)
    assert profile.stage == "Series A"
    assert profile.sector == "FinTech"


def test_pre_seed_healthtech_detected():
    text = "This is a pre-seed raise for a HealthTech company providing telemedicine services."
    profile = ingest_pitch_deck(text)
    assert profile.stage == "pre-seed"
    assert profile.sector == "HealthTech"


def test_unrecognised_sector_defaults_to_other():
    text = "Drone delivery logistics for the agricultural sector — Series B."
    profile = ingest_pitch_deck(text)
    assert profile.sector == "Other"
    assert profile.stage == "Series B"


def test_missing_stage_returns_none():
    text = "We are a SaaS platform for enterprise automation."
    profile = ingest_pitch_deck(text)
    assert profile.stage is None
    assert profile.sector == "SaaS"


def test_never_raises_on_empty_string():
    profile = ingest_pitch_deck("")
    assert isinstance(profile, FounderProfile)


def test_claimed_users_extracted():
    text = "We have 500,000 users on our platform already."
    profile = ingest_pitch_deck(text)
    assert profile.key_signals.get("claimed_users") == 500000
