"""
Multi-Axis Scoring Engine for VC Brain.

Public functions:
  score_founder_axis(profile) -> AxisScore       rule-based, offline-safe
  score_market_axis(profile)  -> AxisScore       rule-based, offline-safe
  score_idea_vs_market_axis(profile) -> AxisScore  LLM-dependent, offline fallback
  run_full_screening(profile, thesis_config) -> ScreeningResult  mixed
  query_founders(query, screened_profiles) -> list[ScreeningResult]  LLM-dependent

All scores are 0-100. Axes are NEVER averaged or combined.
"""
import json
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

from data.decision_engine import AxisScore
from data.founder_data import FounderProfile
from data.founder_signals import generate_founder_signals
from data.risk_flags import RiskFlag, flag_risks
from data.thesis_engine import ThesisConfig, evaluate_founder
from data.parallel_runner import run_agents_parallel

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
_MEMORY_PATH = Path(__file__).parent / "founder_memory.json"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FounderMemory — JSON-file-backed Founder Score persistence
# ---------------------------------------------------------------------------

class FounderMemory:
    """JSON file store keyed by founder identity (github_url or name::company)."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path if path is not None else _MEMORY_PATH

    def _identity(self, profile: FounderProfile) -> str:
        if profile.github_url:
            return profile.github_url
        name = profile.name or ""
        company = profile.company or ""
        return f"{name}::{company}".lower().strip()

    def load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def update(self, identity: str, score: float) -> None:
        store = self.load()
        history = store.get(identity, [])
        history.append(score)
        store[identity] = history
        try:
            self._path.write_text(json.dumps(store, indent=2), encoding="utf-8")
        except OSError:
            pass

    def history(self, identity: str) -> List[float]:
        return self.load().get(identity, [])


# ---------------------------------------------------------------------------
# Intermediate output dataclasses (replace Pydantic — no Pydantic in repo)
# ---------------------------------------------------------------------------

@dataclass
class IdeaVsMarketOutput:
    fit_score: int
    pivot_potential: int
    combined_score: int
    rationale: str
    evidence: List[str]


@dataclass
class FounderQueryOutput:
    matched_indices: List[int]
    reasoning: str


@dataclass
class ScreeningResult:
    profile: FounderProfile
    founder_axis: AxisScore
    market_axis: AxisScore
    idea_vs_market_axis: AxisScore
    risk_flags: List[RiskFlag] = field(default_factory=list)
    thesis_match: bool = False
    thesis_reason: str = ""
    # NOTE: intentionally NO combined_score, total_score, average_score, or weighted_score


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MARKET_OUTLOOK = {
    "ai/ml":        "bullish",
    "fintech":      "bullish",
    "healthtech":   "bullish",
    "cleantech":    "neutral",
    "edtech":       "neutral",
    "saas":         "neutral",
    "other":        "bear",
}

_STAGE_BONUS_STAGES = {"pre-seed", "seed"}

_SIGNAL_WEIGHTS = {
    "commit_frequency":   1.0,
    "star_growth":        1.0,
    "contributor_count":  1.0,
    "recency":            1.0,
    "tech_stack_depth":   1.0,
}


def _founder_identity(profile: FounderProfile) -> str:
    if profile.github_url:
        return profile.github_url
    name = profile.name or ""
    company = profile.company or ""
    return f"{name}::{company}".lower().strip()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _call_ollama(messages: list) -> Optional[str]:
    try:
        resp = requests.post(
            _OLLAMA_URL + "/api/chat",
            json={"model": _OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        return resp.json()["message"]["content"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# score_founder_axis
# ---------------------------------------------------------------------------

def score_founder_axis(profile: FounderProfile) -> AxisScore:
    """
    Score the Founder axis using rule-based signal math + FounderMemory persistence.
    Fully offline — no Ollama needed.
    """
    memory = FounderMemory()
    identity = _founder_identity(profile)
    signals = generate_founder_signals(profile)

    evidence: List[str] = []
    valid_scores: List[float] = []

    for signal_name, data in signals.items():
        direction = data.get("direction", "unknown")
        sig_score = data.get("score", 0)
        if direction != "unknown":
            evidence.append(f"{signal_name}={sig_score} → {direction}")
            valid_scores.append(float(sig_score))

    if not valid_scores:
        current_score = 50.0
        evidence = ["no GitHub signals available"]
    else:
        current_score = sum(valid_scores) / len(valid_scores)

    prior_history = memory.history(identity)
    if not prior_history:
        trend: str = "stable"
    else:
        prior_score = prior_history[-1]
        if current_score > prior_score:
            trend = "improving"
        elif current_score < prior_score:
            trend = "declining"
        else:
            trend = "stable"

    memory.update(identity, current_score)

    return AxisScore(
        name="founder",
        score=current_score,
        trend=trend,
        rationale="signal-based founder score",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# score_market_axis
# ---------------------------------------------------------------------------

def score_market_axis(profile: FounderProfile) -> AxisScore:
    """
    Score the Market axis using sector heuristics and stage bonus.
    Fully offline — no Ollama needed.
    """
    sector = (profile.sector or "other").lower().strip()
    rating = _MARKET_OUTLOOK.get(sector, "bear")

    base_scores = {"bullish": 80, "neutral": 50, "bear": 25}
    score = float(base_scores[rating])

    stage = (profile.stage or "").lower().strip()
    stage_bonus = 5.0 if stage in _STAGE_BONUS_STAGES else 0.0
    score = min(score + stage_bonus, 100.0)

    evidence = [
        f"sector={profile.sector or 'unknown'} → {rating} market outlook",
        f"stage={profile.stage or 'unknown'} → "
        + (f"+{int(stage_bonus)}pt early-entry bonus" if stage_bonus else "no stage bonus"),
    ]

    return AxisScore(
        name="market",
        score=score,
        trend="stable",
        rationale=f"{rating} market for {profile.sector or 'unknown'} at {profile.stage or 'unknown'} stage",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# score_idea_vs_market_axis
# ---------------------------------------------------------------------------

_IDEA_OFFLINE_FALLBACK = AxisScore(
    name="idea_vs_market",
    score=50.0,
    trend="stable",
    rationale="LLM unavailable",
    evidence=["LLM unavailable — rule-based fallback: sector/stage heuristic applied"],
)

_IDEA_PROMPT_TEMPLATE = """\
You are a VC analyst assistant. Evaluate the idea-market fit for this startup.

Sector: {sector}
Stage: {stage}
Key signals: {signals_summary}
Market outlook: {market_rating}

Respond with ONLY a JSON object — no markdown, no explanation:
{{
  "fit_score": <int 0-100, how well idea fits current market>,
  "pivot_potential": <int 0-100, how likely strong team could pivot if needed>,
  "combined_score": <int 0-100, overall idea-vs-market score>,
  "rationale": "<one sentence>",
  "evidence": ["<specific observation 1>", "<specific observation 2>", "<specific observation 3>"]
}}"""


def score_idea_vs_market_axis(profile: FounderProfile) -> AxisScore:
    """
    Score the Idea-vs-Market axis via Ollama LLM call.
    Falls back to score=50, trend='stable' if Ollama is unreachable or returns bad JSON.
    """
    try:
        market = score_market_axis(profile)
        market_rating = market.rationale

        signals_summary = json.dumps(
            {k: v.get("score") for k, v in generate_founder_signals(profile).items()}
        )

        prompt = _IDEA_PROMPT_TEMPLATE.format(
            sector=profile.sector or "unknown",
            stage=profile.stage or "unknown",
            signals_summary=signals_summary,
            market_rating=market_rating,
        )

        content = _call_ollama([{"role": "user", "content": prompt}])
        if content is None:
            return _IDEA_OFFLINE_FALLBACK

        parsed = json.loads(_strip_fences(content))
        output = IdeaVsMarketOutput(
            fit_score=int(parsed["fit_score"]),
            pivot_potential=int(parsed["pivot_potential"]),
            combined_score=int(parsed["combined_score"]),
            rationale=str(parsed["rationale"]),
            evidence=list(parsed["evidence"]),
        )
        return AxisScore(
            name="idea_vs_market",
            score=float(output.combined_score),
            trend="stable",
            rationale=output.rationale,
            evidence=output.evidence,
        )
    except Exception:
        return _IDEA_OFFLINE_FALLBACK


# ---------------------------------------------------------------------------
# run_full_screening
# ---------------------------------------------------------------------------

def run_full_screening(
    profile: FounderProfile,
    thesis_config: Optional[ThesisConfig] = None,
) -> ScreeningResult:
    """
    Run all three axes in parallel, then attach risk flags and thesis match.
    Returns ScreeningResult with all axes uncombined. Never raises.
    """
    try:
        signals = generate_founder_signals(profile)

        dispatch = {
            "founder":       (score_founder_axis, [profile], None),
            "market":        (score_market_axis, [profile], None),
            "idea_vs_market": (score_idea_vs_market_axis, [profile], None),
        }
        results = run_agents_parallel(dispatch, timeout_seconds=130)

        founder_axis = results.get("founder") or AxisScore(
            name="founder", score=50.0, trend="stable", rationale="unavailable", evidence=[]
        )
        market_axis = results.get("market") or AxisScore(
            name="market", score=50.0, trend="stable", rationale="unavailable", evidence=[]
        )
        idea_axis = results.get("idea_vs_market") or AxisScore(
            name="idea_vs_market", score=50.0, trend="stable", rationale="unavailable", evidence=[]
        )

        risk_flags = flag_risks(profile, signals)

        config = thesis_config or ThesisConfig()
        thesis_result = evaluate_founder(profile, config)
        thesis_match = thesis_result.verdict == "PASS"
        if thesis_match:
            thesis_reason = ", ".join(thesis_result.matched_rules)
        else:
            thesis_reason = ", ".join(thesis_result.failed_rules)

        return ScreeningResult(
            profile=profile,
            founder_axis=founder_axis,
            market_axis=market_axis,
            idea_vs_market_axis=idea_axis,
            risk_flags=risk_flags,
            thesis_match=thesis_match,
            thesis_reason=thesis_reason,
        )
    except Exception as exc:
        logger.warning("run_full_screening failed: %s", exc)
        dummy = AxisScore(name="error", score=0.0, trend="stable", rationale="error", evidence=[])
        return ScreeningResult(
            profile=profile,
            founder_axis=dummy,
            market_axis=dummy,
            idea_vs_market_axis=dummy,
        )


# ---------------------------------------------------------------------------
# query_founders
# ---------------------------------------------------------------------------

_QUERY_PROMPT_TEMPLATE = """\
You are a VC analyst assistant. A user wants to find founders matching this query:
"{query}"

Here are the candidates (0-indexed):
{bundles}

Return ONLY a JSON object — no markdown:
{{
  "matched_indices": [<list of 0-based int indices that match the query>],
  "reasoning": "<one sentence explaining the selection>"
}}"""


def query_founders(query: str, screened_profiles: List[ScreeningResult]) -> List[ScreeningResult]:
    """
    Filter a list of ScreeningResult objects using a single compound NL query via Ollama.
    Returns all profiles unchanged if Ollama is unavailable or screened_profiles is empty.
    """
    if not screened_profiles:
        return []

    try:
        bundle_parts = []
        for i, sr in enumerate(screened_profiles):
            all_evidence = (
                sr.founder_axis.evidence
                + sr.market_axis.evidence
                + sr.idea_vs_market_axis.evidence
            )
            evidence_str = "; ".join(all_evidence)
            bundle_parts.append(
                f"[{i}] company={sr.profile.company or 'unknown'} "
                f"sector={sr.profile.sector or 'unknown'}: {evidence_str}"
            )

        prompt = _QUERY_PROMPT_TEMPLATE.format(
            query=query,
            bundles="\n".join(bundle_parts),
        )

        content = _call_ollama([{"role": "user", "content": prompt}])
        if content is None:
            logger.warning("query_founders: Ollama unavailable, returning all profiles")
            return screened_profiles

        parsed = json.loads(_strip_fences(content))
        output = FounderQueryOutput(
            matched_indices=[int(i) for i in parsed["matched_indices"]],
            reasoning=str(parsed.get("reasoning", "")),
        )

        n = len(screened_profiles)
        valid_indices = [i for i in output.matched_indices if 0 <= i < n]
        return [screened_profiles[i] for i in valid_indices]

    except Exception:
        logger.warning("query_founders: error during LLM call, returning all profiles")
        return screened_profiles
