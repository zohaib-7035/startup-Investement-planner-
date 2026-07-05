"""
Scenario simulation using a local Ollama model (free, no API key required).
Requires Ollama running at OLLAMA_URL (default: http://localhost:11434).
Configure model via OLLAMA_MODEL env var (default: llama3.2:3b).

Setup (one-time):
  1. Download Ollama from https://ollama.com
  2. Run: ollama pull llama3.2:3b
  3. Ollama runs automatically as a background service.
"""
import json
import os

import requests

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

_SYSTEM_PROMPT = (
    "You are a macroeconomic and geopolitical risk analyst.\n"
    "Given a plain-language description of a world event, analyse its market impact and return "
    "a JSON object with exactly these six keys:\n"
    "\n"
    "  \"directly_affected_sectors\": a non-empty array of strings naming sectors immediately "
    "impacted (e.g. \"Semiconductors\", \"Defense\")\n"
    "  \"indirectly_affected_sectors\": an array of strings naming sectors with second-order "
    "exposure (may be empty)\n"
    "  \"impacted_companies\": an array of objects, each with exactly three string keys — "
    "\"name\" (company name), \"ticker\" (stock ticker or \"N/A\" if unknown), "
    "\"impact_type\" (e.g. \"Negative\", \"Positive\", \"Mixed\")\n"
    "  \"severity_level\": one of \"LOW\", \"MEDIUM\", \"HIGH\", or \"CRITICAL\"\n"
    "  \"reasoning_chain\": a non-empty ordered array of strings explaining the causal steps\n"
    "  \"confidence_score\": a float between 0.0 and 1.0\n"
    "\n"
    "Return only the raw JSON object. No markdown fences, no commentary, no extra text."
)

_EMPTY_RESULT = {
    "directly_affected_sectors": [],
    "indirectly_affected_sectors": [],
    "impacted_companies": [],
    "severity_level": "MEDIUM",
    "reasoning_chain": [],
    "confidence_score": 0.0,
}

_VALID_SEVERITY_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


def _call_ollama(user_content):
    """Call Ollama chat REST API. Returns response text string, or None on any failure."""
    try:
        resp = requests.post(
            f"{_OLLAMA_URL}/api/chat",
            json={
                "model": _OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        return None


def _parse_llm_response(text):
    try:
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        data = json.loads("\n".join(lines))
        if not isinstance(data, dict):
            return None

        raw_direct = data.get("directly_affected_sectors")
        if not isinstance(raw_direct, list) or not raw_direct:
            return None
        if not all(isinstance(s, str) and s for s in raw_direct):
            return None

        raw_indirect = data.get("indirectly_affected_sectors")
        if not isinstance(raw_indirect, list):
            return None
        indirect = [s for s in raw_indirect if isinstance(s, str)]

        raw_companies = data.get("impacted_companies")
        if not isinstance(raw_companies, list):
            return None
        companies = []
        for item in raw_companies:
            if not isinstance(item, dict):
                continue
            n, t, i = item.get("name"), item.get("ticker"), item.get("impact_type")
            if (isinstance(n, str) and n and isinstance(t, str) and t
                    and isinstance(i, str) and i):
                companies.append({"name": n, "ticker": t, "impact_type": i})

        raw_severity = str(data.get("severity_level", "")).upper()
        severity = raw_severity if raw_severity in _VALID_SEVERITY_LEVELS else "MEDIUM"

        confidence = max(0.0, min(1.0, float(data["confidence_score"])))

        raw_chain = data.get("reasoning_chain")
        if not isinstance(raw_chain, list) or not raw_chain:
            return None
        if not all(isinstance(s, str) for s in raw_chain):
            return None

        return {
            "directly_affected_sectors": list(raw_direct),
            "indirectly_affected_sectors": indirect,
            "impacted_companies": companies,
            "severity_level": severity,
            "reasoning_chain": list(raw_chain),
            "confidence_score": confidence,
        }
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def simulate_scenario(event_description):
    """Returns a 6-key dict describing the market impact of a macroeconomic event. Never raises."""
    if event_description is None or not str(event_description).strip():
        return _EMPTY_RESULT.copy()
    try:
        response_text = _call_ollama(str(event_description))
        if response_text is None:
            return _EMPTY_RESULT.copy()
        parsed = _parse_llm_response(response_text)
        if parsed is None:
            return _EMPTY_RESULT.copy()
        return parsed
    except Exception:
        return _EMPTY_RESULT.copy()
