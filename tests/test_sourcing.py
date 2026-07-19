"""
Tests for data/sourcing.py.
All HTTP calls are mocked — no live network calls required to pass CI.
Mock target: data.sourcing.requests.get (matches the import path in sourcing.py).
"""
import pytest
from unittest.mock import MagicMock, patch

from data.founder_data import FounderProfile
from data.sourcing import (
    FilterRejected,
    activate,
    converge_to_screening,
    inbound_apply,
    load_sample_founders,
    outbound_scan,
)

# ── Filter helpers ────────────────────────────────────────────────────────────

_VALID_DECK = (
    "We are a team of co-founders building a SaaS platform for enterprise automation. "
    "Our product integrates with existing workflows and is used by 500 companies. "
    "We are raising a seed round to accelerate growth."
)

_DECK_WITH_TEAM_NO_PRODUCT = (
    "Our founding team includes experienced operators and domain experts. "
    "The co-founder has 10 years in B2B sales and the CTO has a strong engineering background. "
    "We believe this is an exciting opportunity in a large market."
)

_DECK_WITH_PRODUCT_NO_TEAM = (
    "Our software solution automates data pipelines for enterprise customers. "
    "The platform connects to 50+ data sources and reduces manual work by 80 percent. "
    "Revenue has grown significantly over the past year with strong retention metrics."
)


# ── Test 1: FilterRejected on too-short deck ──────────────────────────────────

def test_filter_rejects_too_short_deck():
    with pytest.raises(FilterRejected) as exc_info:
        inbound_apply("Acme", "Short deck")
    assert exc_info.value.reason == "too_short"


# ── Test 2: FilterRejected on missing team signal ─────────────────────────────

def test_filter_rejects_deck_with_no_team_signal():
    with pytest.raises(FilterRejected) as exc_info:
        inbound_apply("Acme", _DECK_WITH_PRODUCT_NO_TEAM)
    assert exc_info.value.reason == "no_team_signal"


# ── Test 3: FilterRejected on missing product signal ─────────────────────────

def test_filter_rejects_deck_with_no_product_signal():
    with pytest.raises(FilterRejected) as exc_info:
        inbound_apply("Acme", _DECK_WITH_TEAM_NO_PRODUCT)
    assert exc_info.value.reason == "no_product_signal"


# ── Test 4: inbound_apply happy path ─────────────────────────────────────────

def test_inbound_apply_happy_path_returns_profile_with_source_and_company():
    profile = inbound_apply("MyStartup", _VALID_DECK)
    assert isinstance(profile, FounderProfile)
    assert profile.company == "MyStartup"
    assert profile.key_signals["source"] == "inbound"
    assert profile.key_signals["funnel_stage"] == "screening"


# ── Test 5: extra_fields merged into key_signals ──────────────────────────────

def test_inbound_apply_merges_extra_fields_into_key_signals():
    extra = {"claimed_arr": "$2M", "geography": "UK"}
    profile = inbound_apply("Acme", _VALID_DECK, extra_fields=extra)
    assert profile.key_signals["claimed_arr"] == "$2M"
    assert profile.key_signals["geography"] == "UK"


# ── Mock factory for GitHub search ───────────────────────────────────────────

def _mock_github_search(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "items": [
            {
                "name": "awesome-ai",
                "html_url": "https://github.com/ml-labs/awesome-ai",
                "description": "AI agent framework for production systems",
                "stargazers_count": 1200,
                "pushed_at": "2026-07-15T10:00:00Z",
                "owner": {"login": "ml-labs"},
            },
            {
                "name": "agentflow",
                "html_url": "https://github.com/devteam/agentflow",
                "description": "Multi-agent orchestration platform",
                "stargazers_count": 450,
                "pushed_at": "2026-07-10T08:00:00Z",
                "owner": {"login": "devteam"},
            },
        ]
    }
    return resp


# ── Test 6: outbound_scan GitHub path returns structured profiles ──────────────

@patch("data.sourcing.requests.get", side_effect=_mock_github_search)
def test_outbound_scan_github_returns_profiles_with_correct_fields(mock_get):
    profiles = outbound_scan("github", {"q": "AI agent framework", "per_page": 5})
    assert isinstance(profiles, list)
    assert len(profiles) == 2
    assert profiles[0].github_url == "https://github.com/ml-labs/awesome-ai"
    assert profiles[0].company == "awesome-ai"
    assert profiles[1].github_url == "https://github.com/devteam/agentflow"
    assert profiles[1].company == "agentflow"


# ── Test 7: outbound_scan rate limit returns warning sentinel ─────────────────

def _mock_429(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 429
    resp.json.return_value = {}
    return resp


@patch("data.sourcing.requests.get", side_effect=_mock_429)
def test_outbound_scan_rate_limit_returns_partial_with_rate_limit_in_raw_sources(mock_get):
    profiles = outbound_scan("github", {"q": "AI infra", "per_page": 5})
    assert isinstance(profiles, list)
    assert any("rate_limit" in s for p in profiles for s in p.raw_sources)


# ── Test 8: outbound_scan stub sources return empty list ──────────────────────

def test_outbound_scan_stub_sources_return_empty_list_without_raising():
    assert outbound_scan("hacker_news", {"q": "AI"}) == []
    assert outbound_scan("product_hunt", {"q": "AI"}) == []
    assert outbound_scan("unknown_source", {"q": "AI"}) == []


# ── Test 9: activate returns message dict and sets activated flag ─────────────

def test_activate_returns_dict_with_message_and_sets_activated():
    profile = FounderProfile(company="Acme AI", name="Jordan Wu")
    result = activate(profile)

    assert isinstance(result, dict)
    assert "message" in result
    assert "profile" in result
    message = result["message"]
    assert len(message) > 0
    assert "Acme AI" in message or "Jordan Wu" in message
    assert result["profile"].key_signals["activated"] is True
    assert result["profile"].key_signals["source"] == "outbound"


# ── Test 10: load_sample_founders: count, company, sectors, contradictions, sources

def test_load_sample_founders_returns_at_least_15_profiles_with_company():
    founders = load_sample_founders()
    assert len(founders) >= 15
    assert all(f.company is not None for f in founders)
    # AC: ≥3 distinct sector values present
    assert len({f.sector for f in founders if f.sector}) >= 3
    # AC: ≥3 seeded contradiction profiles (claimed_users > 10,000 AND total_stars < 10)
    contradictions = [
        f for f in founders
        if (f.key_signals.get("claimed_users") or 0) > 10_000
        and (f.key_signals.get("total_stars") or 999) < 10
    ]
    assert len(contradictions) >= 3
    # AC: both source="inbound" and source="outbound" represented
    sources_present = {f.key_signals.get("source") for f in founders}
    assert "inbound" in sources_present
    assert "outbound" in sources_present


# ── Test 11: converge_to_screening sets funnel_stage and preserves source ─────

def test_converge_to_screening_sets_funnel_stage_and_preserves_source():
    # Source set by caller (inbound_apply / activate) before converge is called
    inbound_profile = FounderProfile(
        company="TestCo", key_signals={"source": "inbound"}
    )
    result = converge_to_screening(inbound_profile)
    assert result.key_signals["funnel_stage"] == "screening"
    assert result.key_signals["source"] == "inbound"
    assert result is inbound_profile  # tag-and-passthrough — same object returned


# ── Test 12: converge_to_screening does not inject scoring module fields ───────

def test_converge_to_screening_adds_no_scoring_module_fields():
    profile = FounderProfile(company="CleanSlate", key_signals={"source": "inbound"})
    before_keys = set(profile.key_signals.keys())
    converge_to_screening(profile)
    added_keys = set(profile.key_signals.keys()) - before_keys
    # Only funnel_stage should be added — no scoring outputs
    assert added_keys == {"funnel_stage"}
    for scoring_key in ("signals", "thesis_result", "risk_flags", "decision", "axis_scores"):
        assert scoring_key not in profile.key_signals


# ── Test 13: outbound path: activate → converge preserves source="outbound" ───

def test_outbound_path_activate_then_converge_to_screening_sets_outbound_source_and_funnel():
    profile = FounderProfile(company="OutboundCo", name="Dev User")
    activate_result = activate(profile)
    final_profile = converge_to_screening(activate_result["profile"])

    assert final_profile.key_signals["source"] == "outbound"
    assert final_profile.key_signals["funnel_stage"] == "screening"
    assert final_profile.key_signals["activated"] is True


# ── Test 14: load_sample_founders returns [] when file is missing ─────────────

def test_load_sample_founders_returns_empty_list_when_file_not_found():
    with patch("builtins.open", side_effect=FileNotFoundError("no such file")):
        founders = load_sample_founders()
    assert founders == []
