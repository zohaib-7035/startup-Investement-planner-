"""
Founder signal scoring — five signals derived from FounderProfile.key_signals.
Each signal returns a score (0-100 or None) and a direction string.
Never raises.
"""
from typing import Optional
from data.founder_data import FounderProfile

_UNKNOWN = {"score": None, "direction": "unknown"}


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _score_commit_frequency(commits_per_week: Optional[float]) -> dict:
    """Weekly commit average over last 12 weeks vs typical baseline."""
    v = _safe_float(commits_per_week)
    if v is None:
        return _UNKNOWN.copy()
    if v >= 10:
        return {"score": 90, "direction": "bullish"}
    if v >= 5:
        return {"score": 70, "direction": "bullish"}
    if v >= 1:
        return {"score": 50, "direction": "neutral"}
    return {"score": 20, "direction": "bearish"}


def _score_star_growth(stars_per_repo: Optional[float]) -> dict:
    """Average stars per repo — proxy for velocity/community interest."""
    v = _safe_float(stars_per_repo)
    if v is None:
        return _UNKNOWN.copy()
    if v >= 500:
        return {"score": 95, "direction": "bullish"}
    if v >= 100:
        return {"score": 75, "direction": "bullish"}
    if v >= 20:
        return {"score": 50, "direction": "neutral"}
    return {"score": 20, "direction": "bearish"}


def _score_contributor_count(count: Optional[float]) -> dict:
    """Number of unique contributors to the top repo."""
    v = _safe_float(count)
    if v is None:
        return _UNKNOWN.copy()
    if v >= 10:
        return {"score": 90, "direction": "bullish"}
    if v >= 3:
        return {"score": 60, "direction": "neutral"}
    if v >= 2:
        return {"score": 40, "direction": "neutral"}
    # Solo founder — known risk signal
    return {"score": 15, "direction": "bearish"}


def _score_recency(days_since_push: Optional[float]) -> dict:
    """Days since last commit to the top repo."""
    v = _safe_float(days_since_push)
    if v is None:
        return _UNKNOWN.copy()
    if v <= 7:
        return {"score": 95, "direction": "bullish"}
    if v <= 30:
        return {"score": 75, "direction": "bullish"}
    if v <= 90:
        return {"score": 50, "direction": "neutral"}
    if v <= 180:
        return {"score": 30, "direction": "bearish"}
    return {"score": 10, "direction": "bearish"}


def _score_tech_stack_depth(language_count: Optional[float]) -> dict:
    """Number of distinct programming languages across public repos."""
    v = _safe_float(language_count)
    if v is None:
        return _UNKNOWN.copy()
    if v >= 5:
        return {"score": 85, "direction": "bullish"}
    if v >= 3:
        return {"score": 65, "direction": "neutral"}
    if v >= 1:
        return {"score": 45, "direction": "neutral"}
    return {"score": 20, "direction": "bearish"}


def generate_founder_signals(profile: FounderProfile) -> dict:
    """
    Compute five founder signals from FounderProfile.key_signals.
    Returns a dict mapping signal name → {score, direction}.
    Signals with missing inputs return score=None, direction='unknown'.
    Never raises.
    """
    try:
        ks = profile.key_signals or {}
        return {
            "commit_frequency":  _score_commit_frequency(ks.get("commit_frequency")),
            "star_growth":       _score_star_growth(ks.get("star_growth")),
            "contributor_count": _score_contributor_count(ks.get("contributor_count")),
            "recency":           _score_recency(ks.get("recency")),
            "tech_stack_depth":  _score_tech_stack_depth(ks.get("tech_stack_depth")),
        }
    except Exception:
        return {
            "commit_frequency":  _UNKNOWN.copy(),
            "star_growth":       _UNKNOWN.copy(),
            "contributor_count": _UNKNOWN.copy(),
            "recency":           _UNKNOWN.copy(),
            "tech_stack_depth":  _UNKNOWN.copy(),
        }
