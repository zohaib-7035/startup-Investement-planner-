"""
Founder data ingestion — GitHub REST API v3 and pitch deck text/PDF.
Returns FounderProfile dataclass. Never raises.
"""
import datetime
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

_GITHUB_API = "https://api.github.com"
_MAX_REPOS = 10
_TIMEOUT = 10

_SECTOR_KEYWORDS = {
    "FinTech":    ["fintech", "finance", "payment", "banking", "lending", "insurance", "crypto", "defi", "neobank"],
    "HealthTech": ["health", "medical", "clinical", "pharma", "biotech", "wellness", "telemedicine", "diagnostics"],
    "EdTech":     ["education", "learning", "school", "university", "course", "training", "edtech", "tutoring"],
    "CleanTech":  ["clean", "green", "renewable", "energy", "solar", "sustainability", "climate", "carbon"],
    "SaaS":       ["saas", "software", "platform", "tool", "automation", "workflow", "b2b", "enterprise"],
}

_STAGE_PATTERNS = [
    (r'\bpre[-\s]?seed\b',  "pre-seed"),
    (r'\bseries\s+c\+?\b',  "Series C+"),
    (r'\bseries\s+b\b',     "Series B"),
    (r'\bseries\s+a\b',     "Series A"),
    (r'\bseed\b',           "seed"),
]


@dataclass
class FounderProfile:
    name: Optional[str] = None
    company: Optional[str] = None
    sector: Optional[str] = None
    stage: Optional[str] = None
    github_url: Optional[str] = None
    key_signals: dict = field(default_factory=dict)
    raw_sources: list = field(default_factory=list)


def fetch_github_profile(username_or_org: str) -> FounderProfile:
    """
    Fetch founder/org data from GitHub REST API (unauthenticated).
    Caps at _MAX_REPOS to stay within 60 req/hour rate limit.
    Returns FounderProfile with key_signals populated. Never raises.
    """
    profile = FounderProfile(
        github_url=f"https://github.com/{username_or_org}",
        raw_sources=[],
    )
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}

        user_url = f"{_GITHUB_API}/users/{username_or_org}"
        resp = requests.get(user_url, headers=headers, timeout=_TIMEOUT)
        if resp.status_code in (403, 429):
            profile.raw_sources.append(f"rate-limited at {user_url}")
            return profile
        if resp.status_code != 200:
            profile.raw_sources.append(f"user not found: {user_url} (status {resp.status_code})")
            return profile

        user_data = resp.json()
        profile.name = user_data.get("name") or username_or_org
        profile.company = user_data.get("company")
        profile.raw_sources.append(user_url)

        repos_url = (
            f"{_GITHUB_API}/users/{username_or_org}/repos"
            f"?sort=stars&per_page={_MAX_REPOS}&type=public"
        )
        resp = requests.get(repos_url, headers=headers, timeout=_TIMEOUT)
        if resp.status_code in (403, 429):
            profile.raw_sources.append(f"rate-limited at {repos_url}")
            return profile

        repos = resp.json() if resp.status_code == 200 else []
        profile.raw_sources.append(repos_url)

        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        languages = sorted({r.get("language") for r in repos if r.get("language")})

        # Days since most recently pushed repo
        days_since_push = None
        if repos:
            latest_push = repos[0].get("pushed_at", "")
            if latest_push:
                try:
                    pushed = datetime.datetime.fromisoformat(latest_push.replace("Z", "+00:00"))
                    now = datetime.datetime.now(datetime.timezone.utc)
                    days_since_push = (now - pushed).days
                except Exception:
                    pass

        # Contributor count from the top-starred repo only (1 extra request)
        contributor_count = None
        if repos:
            top_repo = repos[0]["name"]
            contrib_url = f"{_GITHUB_API}/repos/{username_or_org}/{top_repo}/contributors?per_page=100"
            resp = requests.get(contrib_url, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 200:
                contributor_count = len(resp.json())
                profile.raw_sources.append(contrib_url)
            elif resp.status_code in (403, 429):
                profile.raw_sources.append(f"rate-limited at {contrib_url}")

        # Star growth: total stars / number of repos (proxy for velocity)
        star_growth = round(total_stars / len(repos), 2) if repos else 0.0

        # Commit frequency from weekly commit activity of top repo (1 extra request)
        commit_frequency = None
        if repos:
            top_repo = repos[0]["name"]
            activity_url = f"{_GITHUB_API}/repos/{username_or_org}/{top_repo}/stats/commit_activity"
            resp = requests.get(activity_url, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 200:
                weeks = resp.json() or []
                recent = weeks[-12:] if len(weeks) >= 12 else weeks
                commit_frequency = round(sum(w.get("total", 0) for w in recent) / max(len(recent), 1), 2)
                profile.raw_sources.append(activity_url)

        profile.key_signals = {
            "commit_frequency":  commit_frequency,
            "star_growth":       star_growth,
            "contributor_count": contributor_count,
            "recency":           days_since_push,
            "tech_stack_depth":  len(languages),
            "total_stars":       total_stars,
            "languages":         languages,
            "repo_count":        len(repos),
        }

    except Exception as exc:
        profile.raw_sources.append(f"error: {exc}")

    return profile


def ingest_pitch_deck(text_or_path: str) -> FounderProfile:
    """
    Parse a pitch deck from a PDF file path or raw text string.
    Extracts sector, stage, company name, and any user-count claims.
    Never raises.
    """
    profile = FounderProfile(raw_sources=[])
    try:
        stripped = text_or_path.strip()
        if stripped.lower().endswith(".pdf"):
            try:
                import PyPDF2
                with open(stripped, "rb") as fh:
                    reader = PyPDF2.PdfReader(fh)
                    text = " ".join(
                        (page.extract_text() or "") for page in reader.pages
                    )
                profile.raw_sources.append(f"pdf:{stripped}")
            except Exception as pdf_exc:
                profile.raw_sources.append(f"pdf-read-error: {pdf_exc}")
                return profile
        else:
            text = stripped
            profile.raw_sources.append("pitch_deck_text")

        lower = text.lower()

        # Stage detection — most specific pattern wins
        for pattern, label in _STAGE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                profile.stage = label
                break

        # Sector detection — first matching keyword set wins
        for sector_name, keywords in _SECTOR_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                profile.sector = sector_name
                break
        if profile.sector is None:
            profile.sector = "Other"

        # Company name heuristic
        company_match = re.search(
            r'(?:company|startup|we are|introducing|meet)[:\s]+([A-Z][a-zA-Z0-9\s&]{2,30})',
            text,
        )
        if company_match:
            profile.company = company_match.group(1).strip()

        # User/customer count claim — stored for risk flagging
        user_match = re.search(r'(\d[\d,]*)\s*(?:users|customers|clients)', lower)
        claimed_users = None
        if user_match:
            try:
                claimed_users = int(user_match.group(1).replace(",", ""))
            except ValueError:
                pass

        profile.key_signals = {"claimed_users": claimed_users}

    except Exception as exc:
        profile.raw_sources.append(f"error: {exc}")

    return profile
