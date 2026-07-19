"""
Founder Sourcing Pipeline — two entry points, one funnel.

inbound_apply()  : submitted pitch deck → FounderProfile (with junk filter)
outbound_scan()  : GitHub search → list[FounderProfile]
activate()       : simulate cold outreach, tag profile as outbound
converge_to_screening() : single convergence gate before scoring

Real API calls  : GitHub /search/repositories (unauthenticated, 60 req/hr)
Stubbed         : Hacker News connector, ProductHunt connector
Synthetic demo  : load_sample_founders() from data/sample_founders.json
"""
import datetime
import json
import logging
import pathlib
from typing import List, Optional

import requests

from data.founder_data import FounderProfile, _SECTOR_KEYWORDS, ingest_pitch_deck

log = logging.getLogger(__name__)

# ── Tunable constants — adjust before a demo ──────────────────────────────────

_MIN_DECK_LENGTH = 50

_TEAM_KEYWORDS = ["co-founder", "team", "ceo", "cto", "founder"]

_PRODUCT_KEYWORDS = ["product", "solution", "platform", "app", "tool", "service"]

_OUTREACH_TEMPLATE = (
    "Hi {name},\n\n"
    "We came across {company} on GitHub and were impressed by what you're building. "
    "The technical signals suggest strong early momentum, and we'd love to learn more "
    "about your roadmap.\n\n"
    "Would you be open to a 20-minute call this week?\n\n"
    "Best,\nVC Brain Team"
)

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}
_TIMEOUT = 10
_MAX_RESULTS = 10


# ── Exception ─────────────────────────────────────────────────────────────────

class FilterRejected(Exception):
    """
    Raised by inbound_apply() when the fast first-pass filter rejects a submission.
    This is a control-flow signal, not an error — callers must catch it.

    Attributes:
        reason: one of "too_short", "no_team_signal", "no_product_signal"
    """
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ── Internal helpers ──────────────────────────────────────────────────────────

def _first_pass_filter(deck_text: str) -> None:
    """
    Lightweight junk filter. Checks length first (avoids keyword parsing on empty input),
    then team-signal presence, then product-signal presence.
    Raises FilterRejected with an explicit reason on any failure.
    """
    stripped = deck_text.strip()
    if len(stripped) < _MIN_DECK_LENGTH:
        raise FilterRejected("too_short")
    lower = stripped.lower()
    if not any(kw in lower for kw in _TEAM_KEYWORDS):
        raise FilterRejected("no_team_signal")
    if not any(kw in lower for kw in _PRODUCT_KEYWORDS):
        raise FilterRejected("no_product_signal")


def _sector_from_text(text: str) -> Optional[str]:
    """Match text against the shared _SECTOR_KEYWORDS dict. Returns first match or None."""
    lower = (text or "").lower()
    for sector_name, keywords in _SECTOR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return sector_name
    return None


def _days_since(iso_timestamp: str) -> Optional[int]:
    """Return integer days elapsed since an ISO-8601 UTC timestamp. None on parse failure."""
    try:
        pushed = datetime.datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.timezone.utc) - pushed).days
    except Exception:
        return None


# ── Funnel convergence (defined before callers) ───────────────────────────────

def converge_to_screening(founder_profile: FounderProfile) -> FounderProfile:
    """
    Single convergence gate for both inbound and outbound sourcing paths.
    Tags the profile with funnel_stage="screening" and returns it.
    Does not import or call any scoring module. Never raises.
    """
    founder_profile.key_signals["funnel_stage"] = "screening"
    return founder_profile


# ── Inbound path ──────────────────────────────────────────────────────────────

def inbound_apply(
    company_name: str,
    deck_text: str,
    extra_fields: Optional[dict] = None,
) -> FounderProfile:
    """
    Inbound application entry point.

    Runs the fast first-pass filter, then delegates deck parsing to ingest_pitch_deck().
    Overrides profile.company with the explicit company_name argument (takes priority over
    any company name extracted by the parser). Merges extra_fields into key_signals if
    provided. Tags the profile source="inbound" and routes through converge_to_screening().

    Raises:
        FilterRejected: if the deck fails the fast filter. Callers must handle this.
    """
    _first_pass_filter(deck_text)
    profile = ingest_pitch_deck(deck_text)
    profile.company = company_name
    if extra_fields:
        profile.key_signals.update(extra_fields)
    profile.key_signals["source"] = "inbound"
    return converge_to_screening(profile)


# ── Outbound path ─────────────────────────────────────────────────────────────

def _scan_github(query_params: dict) -> List[FounderProfile]:
    """
    Query GitHub /search/repositories and map each result to a FounderProfile.
    Returns partial results (possibly empty) on 403/429 with a rate_limit sentinel profile.
    """
    q = str(query_params.get("q", "")).strip()
    sort = str(query_params.get("sort", "stars"))
    per_page = min(int(query_params.get("per_page", _MAX_RESULTS)), _MAX_RESULTS)

    params = {"q": q, "sort": sort, "per_page": per_page}
    try:
        resp = requests.get(
            _GITHUB_SEARCH_URL, params=params, headers=_GITHUB_HEADERS, timeout=_TIMEOUT
        )
    except Exception as exc:
        log.warning("_scan_github: network error: %s", exc)
        return []

    if resp.status_code in (403, 429):
        log.warning("_scan_github: rate limited (HTTP %s)", resp.status_code)
        sentinel = FounderProfile(raw_sources=["rate_limit"])
        return [sentinel]

    if resp.status_code != 200:
        log.warning("_scan_github: unexpected status %s", resp.status_code)
        return []

    profiles: List[FounderProfile] = []
    for item in (resp.json().get("items") or [])[:per_page]:
        description = item.get("description") or ""
        owner_login = (item.get("owner") or {}).get("login", "")
        profile = FounderProfile(
            name=owner_login,
            company=item.get("name", ""),
            github_url=item.get("html_url", ""),
            sector=_sector_from_text(description),
            raw_sources=[item.get("html_url", "")],
            key_signals={
                "source":       "outbound",
                "total_stars":  item.get("stargazers_count", 0),
                "recency_days": _days_since(item.get("pushed_at", "")),
                "description":  description,
            },
        )
        profiles.append(profile)
    return profiles


def outbound_scan(source: str, query_params: dict) -> List[FounderProfile]:
    """
    Outbound scan entry point. Returns a list of FounderProfile objects.
    Never raises — all errors return an empty list.

    source="github":
        Queries GitHub /search/repositories (unauthenticated, 60 req/hr limit).
        Per-repo signal enrichment (commit history, contributors) is deferred to the
        scoring step; this call retrieves description-level signals only.

    source="hacker_news":
        Stub. Real implementation: Algolia HN Search API at
        https://hn.algolia.com/api/v1/search?query=<q>&tags=show_hn
        No API key required. Would need to map HN post title + URL to FounderProfile.

    source="product_hunt":
        Stub. Real implementation: ProductHunt GraphQL API at
        https://api.producthunt.com/v2/api/graphql
        Requires an OAuth client_token from https://www.producthunt.com/v2/oauth/applications

    Any other source string returns an empty list.
    """
    try:
        if source == "github":
            return _scan_github(query_params)
        if source in ("hacker_news", "product_hunt"):
            return []
        return []
    except Exception as exc:
        log.warning("outbound_scan(%s): unexpected error: %s", source, exc)
        return []


# ── Activation ────────────────────────────────────────────────────────────────

def activate(founder_profile: FounderProfile) -> dict:
    """
    Simulate cold outreach for an outbound-discovered founder.
    Intended for outbound profiles only (produced by outbound_scan()).

    Sets key_signals["activated"]=True and key_signals["source"]="outbound".
    Formats _OUTREACH_TEMPLATE into a message string.
    Does NOT send real emails or make any HTTP request.

    Returns:
        {"message": str, "profile": FounderProfile}
    """
    founder_profile.key_signals["activated"] = True
    founder_profile.key_signals["source"] = "outbound"
    message = _OUTREACH_TEMPLATE.format(
        name=founder_profile.name or "Founder",
        company=founder_profile.company or "your company",
    )
    return {"message": message, "profile": founder_profile}


# ── Synthetic demo dataset ────────────────────────────────────────────────────

def load_sample_founders() -> List[FounderProfile]:
    """
    Load synthetic demo profiles from data/sample_founders.json.
    Returns an empty list if the file is missing or malformed. Never raises.
    """
    try:
        json_path = pathlib.Path(__file__).parent / "sample_founders.json"
        with open(json_path, "r", encoding="utf-8") as fh:
            items = json.load(fh)
        return [FounderProfile(**item) for item in items]
    except FileNotFoundError:
        log.warning("load_sample_founders: sample_founders.json not found at %s", json_path)
        return []
    except Exception as exc:
        log.warning("load_sample_founders: failed to deserialise profiles: %s", exc)
        return []
