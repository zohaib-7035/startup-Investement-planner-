"""
Claim extraction and trust-score verification for VC Brain.

extract_claims(profile) -> list[Claim]      LLM-dependent, offline fallback
verify_claim(claim, available_evidence)
    -> VerifiedClaim                         rule-based, always offline-safe

Adapts knowledge_graph.py Ollama pattern with a VC-oriented prompt.
Never raises from either public function.
"""
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import requests

from data.founder_data import FounderProfile

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

_CLAIM_CATEGORIES = frozenset({"traction", "revenue", "team", "market_size", "other"})

# Sections that must be explicitly flagged "not disclosed" when absent
_GAP_SECTIONS = ["cap_table", "financials", "revenue"]

_CLAIM_SYSTEM_PROMPT = (
    "You are a VC due-diligence analyst. "
    "Read the provided founder or pitch deck text and extract every factual claim the founder makes. "
    "For each claim return a JSON array where every element has exactly four keys: "
    '"claim_text" (string — the exact claim, concise), '
    '"category" (one of: traction, revenue, team, market_size, other), '
    '"confidence_score" (float 0.0–1.0 — your confidence that this is a genuine, specific claim), '
    '"source_reference" (string — brief label for which part of the text this came from). '
    "If no claims are present return []. Return ONLY the JSON array — no other text."
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    claim_text: str
    category: str
    confidence_score: float
    source_reference: str


@dataclass
class VerifiedClaim:
    claim: Claim
    status: str  # "verified" | "unverifiable" | "contradicted"
    verification_confidence: float
    supporting_evidence: List[str] = field(default_factory=list)
    contradiction_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_ollama_for_claims(text: str) -> Optional[str]:
    try:
        resp = requests.post(
            f"{_OLLAMA_URL}/api/chat",
            json={
                "model": _OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _CLAIM_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract all factual claims from:\n\n{text}"},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        return None


def _parse_claims_response(text: str) -> List[Claim]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = [l for l in stripped.splitlines() if not l.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    if not stripped.startswith("["):
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start != -1 and end != -1:
            stripped = stripped[start:end + 1]
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, dict):
        for key in ("claims", "results", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    claims = []
    for item in data:
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("claim_text", "")).strip()
        category = str(item.get("category", "other")).strip().lower()
        if category not in _CLAIM_CATEGORIES:
            category = "other"
        try:
            confidence_score = max(0.0, min(1.0, float(item.get("confidence_score", 0.7))))
        except (TypeError, ValueError):
            confidence_score = 0.7
        source_reference = str(item.get("source_reference", "pitch_deck")).strip()
        if claim_text:
            claims.append(Claim(
                claim_text=claim_text,
                category=category,
                confidence_score=confidence_score,
                source_reference=source_reference,
            ))
    return claims


def _gap_flag_claims(existing_claims: List[Claim], profile: FounderProfile) -> List[Claim]:
    """Emit a 'not disclosed' claim for each _GAP_SECTIONS entry with no evidence."""
    signals = profile.key_signals or {}
    gap_claims = []
    for section in _GAP_SECTIONS:
        # Check whether any existing claim covers this section
        covered = any(
            section.replace("_", " ") in c.claim_text.lower() or
            section in c.source_reference.lower()
            for c in existing_claims
        )
        # Also check key_signals for direct evidence
        if not covered:
            if section == "revenue" and ("revenue" in signals or "arr" in signals or "mrr" in signals):
                covered = True
            elif section == "financials" and ("revenue" in signals or "funding" in signals):
                covered = True
            elif section == "cap_table" and ("cap_table" in signals or "ownership" in signals):
                covered = True
        if not covered:
            gap_claims.append(Claim(
                claim_text="not disclosed",
                category="other",
                confidence_score=1.0,
                source_reference=f"{section}: not disclosed in profile data",
            ))
    return gap_claims


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def _synthesize_signal_claims(profile: FounderProfile) -> List[Claim]:
    """
    Build structured Claim objects from key_signals data.
    Gives the memo meaningful content even when no pitch deck text is available.
    """
    ks = profile.key_signals or {}
    company = profile.company or profile.name or "the company"
    claims: List[Claim] = []

    claimed_users = ks.get("claimed_users")
    if claimed_users and int(claimed_users) > 0:
        claims.append(Claim(
            claim_text=f"{company} has {int(claimed_users):,} active users on the platform",
            category="traction",
            confidence_score=0.80,
            source_reference="key_signals.claimed_users",
        ))

    total_stars = ks.get("total_stars")
    if total_stars is not None and int(total_stars) > 0:
        claims.append(Claim(
            claim_text=f"{company} GitHub repository has {int(total_stars):,} stars",
            category="traction",
            confidence_score=0.95,
            source_reference="key_signals.total_stars",
        ))

    commit_freq = ks.get("commit_frequency")
    if commit_freq and float(commit_freq) > 0:
        claims.append(Claim(
            claim_text=f"Engineering team commits {float(commit_freq):.1f}× per week on average",
            category="team",
            confidence_score=0.90,
            source_reference="key_signals.commit_frequency",
        ))

    contributor_count = ks.get("contributor_count")
    if contributor_count and int(contributor_count) > 1:
        claims.append(Claim(
            claim_text=f"Project has {int(contributor_count)} active contributors on GitHub",
            category="team",
            confidence_score=0.90,
            source_reference="key_signals.contributor_count",
        ))

    recency = ks.get("recency")
    recency_days = ks.get("recency_days")
    last_push = recency or recency_days
    if last_push is not None:
        days = int(last_push)
        if days <= 7:
            label = f"last pushed {days} day{'s' if days != 1 else ''} ago — actively maintained"
        elif days <= 30:
            label = f"last pushed {days} days ago — recently active"
        else:
            label = f"last pushed {days} days ago — low recent activity"
        claims.append(Claim(
            claim_text=f"{company} repository {label}",
            category="traction",
            confidence_score=0.95,
            source_reference="key_signals.recency",
        ))

    sector = profile.sector
    stage = profile.stage
    if sector:
        claims.append(Claim(
            claim_text=f"{company} operates in the {sector} sector at {stage or 'unspecified'} stage",
            category="market_size",
            confidence_score=0.95,
            source_reference="profile.sector",
        ))

    return claims


def extract_claims(profile: FounderProfile) -> List[Claim]:
    """
    Extract structured claims from profile.raw_sources text using Ollama.
    Always supplements with signal-derived claims from key_signals.
    Offline fallback: signal claims + gap flags only.
    Never raises.
    """
    try:
        # Identify pitch deck / bio text (length > 100, not a URL)
        text_items = [
            s for s in (profile.raw_sources or [])
            if isinstance(s, str) and len(s) > 100 and not s.strip().startswith("http")
        ]
        llm_claims: List[Claim] = []
        for text in text_items:
            raw = _call_ollama_for_claims(text)
            if raw:
                llm_claims.extend(_parse_claims_response(raw))

        signal_claims = _synthesize_signal_claims(profile)
        # Deduplicate: drop signal claim if LLM already extracted a claim with same category + similar text
        llm_cats = {c.claim_text.lower()[:40] for c in llm_claims}
        unique_signal = [c for c in signal_claims if c.claim_text.lower()[:40] not in llm_cats]

        all_claims = llm_claims + unique_signal
        gap_claims = _gap_flag_claims(all_claims, profile)
        return all_claims + gap_claims
    except Exception:
        try:
            sig = _synthesize_signal_claims(profile)
            return sig + _gap_flag_claims(sig, profile)
        except Exception:
            return []


def verify_claim(claim: Claim, available_evidence: list) -> VerifiedClaim:
    """
    Rule-based cross-check of a single claim against available_evidence.
    available_evidence: list[dict] — signal dicts {signal, score, direction}
                        or claim refs  {claim_text, category, confidence_score}
    Never raises.
    """
    try:
        # "not disclosed" claims are always unverifiable with certainty
        if claim.claim_text.strip().lower() == "not disclosed":
            return VerifiedClaim(
                claim=claim,
                status="unverifiable",
                verification_confidence=1.0,
                supporting_evidence=["Gap flagged: data absent from profile"],
            )

        src = claim.source_reference.lower()

        # Claims derived directly from observed GitHub signals are verified facts,
        # except claimed_users which is self-reported by the founder.
        if src.startswith("key_signals.") and "claimed_users" not in src:
            return VerifiedClaim(
                claim=claim,
                status="verified",
                verification_confidence=0.95,
                supporting_evidence=[f"Directly observed signal: {claim.source_reference}"],
            )

        # Profile metadata (sector, stage) is a known fact from the profile record.
        if src.startswith("profile."):
            return VerifiedClaim(
                claim=claim,
                status="verified",
                verification_confidence=0.95,
                supporting_evidence=[f"Confirmed profile field: {claim.source_reference}"],
            )

        # Index signals by name for fast lookup
        signal_map = {
            item["signal"]: item
            for item in available_evidence
            if "signal" in item and "score" in item
        }

        # ── Traction claims (self-reported numbers, e.g. claimed_users) ───
        if claim.category == "traction":
            num_match = re.search(r"\b(\d[\d,]*)\s*([KkMmBb]?)\s*(users?|customers?|downloads?)?", claim.claim_text)
            claimed_number = 0
            if num_match:
                raw_num = num_match.group(1).replace(",", "")
                multiplier_char = (num_match.group(2) or "").upper()
                multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(multiplier_char, 1)
                try:
                    claimed_number = int(raw_num) * multiplier
                except ValueError:
                    claimed_number = 0

            star_signal = signal_map.get("star_growth") or signal_map.get("total_stars")
            if star_signal is not None:
                star_score = float(star_signal.get("score", 0))
                if star_score <= 20 and claimed_number > 10_000:
                    return VerifiedClaim(
                        claim=claim,
                        status="contradicted",
                        verification_confidence=0.9,
                        supporting_evidence=[],
                        contradiction_note=(
                            f"Claim asserts {claimed_number:,} users/traction but "
                            f"{star_signal['signal']} signal score is only {star_score:.0f}/100 — "
                            "very low GitHub traction contradicts large user base claim."
                        ),
                    )
                return VerifiedClaim(
                    claim=claim,
                    status="unverifiable",
                    verification_confidence=0.4,
                    supporting_evidence=[f"{star_signal['signal']} score: {star_score:.0f}"],
                )
            return VerifiedClaim(
                claim=claim,
                status="unverifiable",
                verification_confidence=0.0,
                supporting_evidence=[],
            )

        # ── Team claims ────────────────────────────────────────────────────
        if claim.category == "team":
            return VerifiedClaim(
                claim=claim,
                status="unverifiable",
                verification_confidence=0.0,
                supporting_evidence=[],
            )

        # ── Revenue / market_size claims — no rule-based signal match ─────
        if claim.category in ("revenue", "market_size"):
            return VerifiedClaim(
                claim=claim,
                status="unverifiable",
                verification_confidence=0.0,
                supporting_evidence=[],
            )

        # ── Default ────────────────────────────────────────────────────────
        return VerifiedClaim(
            claim=claim,
            status="unverifiable",
            verification_confidence=0.0,
            supporting_evidence=[],
        )

    except Exception:
        return VerifiedClaim(
            claim=claim,
            status="unverifiable",
            verification_confidence=0.0,
            supporting_evidence=[],
        )
