"""
Knowledge graph triple extraction using local Ollama (free, no API key).
Requires Ollama running at OLLAMA_URL (default: http://localhost:11434).
Falls back to an empty list if Ollama is unavailable.
"""
import json
import os
from typing import Dict, List, Optional

import requests

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

_SYSTEM_PROMPT = (
    "You are a financial knowledge graph extraction agent. "
    "Read the provided text and extract all financially meaningful relationships between entities. "
    "For each relationship identify: source entity, target entity, relationship type. "
    "Return ONLY a JSON array where each element has exactly four keys: "
    '"source" (string), '
    '"relation" (string — upper-case, e.g. SUPPLIER, COMPETITOR, SUBSIDIARY, PARTNER, CUSTOMER, '
    "MANUFACTURER, INVESTOR, ACQUIRER), "
    '"target" (string), '
    '"confidence" (float 0.0–1.0). '
    "If no relationships are present return []. No other text outside the JSON array."
)

_TRIPLE_STRING_KEYS = ("source", "relation", "target")


def _call_ollama(text: str) -> Optional[str]:
    try:
        resp = requests.post(
            f"{_OLLAMA_URL}/api/chat",
            json={
                "model": _OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract financial relationships from:\n\n{text}"},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        return None


def _parse_llm_response(text: str) -> List[Dict]:
    stripped = text.strip()
    # Strip markdown code fences
    if stripped.startswith("```"):
        lines = [l for l in stripped.splitlines() if not l.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    # Extract first [...] array if model added surrounding text
    if not stripped.startswith("["):
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start != -1 and end != -1:
            stripped = stripped[start:end + 1]
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return []
    # Handle {"relationships": [...]} or {"triples": [...]} wrapper
    if isinstance(data, dict):
        for key in ("relationships", "triples", "entities", "results", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            valid = all(
                isinstance(item.get(k), str) and item.get(k).strip()
                for k in _TRIPLE_STRING_KEYS
            )
            if not valid:
                continue
            try:
                clamped_conf = max(0.0, min(1.0, float(item.get("confidence", 0.8))))
            except (TypeError, ValueError):
                clamped_conf = 0.8
        except (TypeError, ValueError):
            continue
        results.append({
            "source": item["source"].strip(),
            "relation": item["relation"].strip().upper(),
            "target": item["target"].strip(),
            "confidence": clamped_conf,
        })
    return results


def extract_relationships(text: str) -> List[Dict]:
    """Extract financial entity relationships from text using local Ollama. Never raises."""
    if not text or not str(text).strip():
        return []
    try:
        response_text = _call_ollama(str(text))
        if response_text is None:
            return []
        return _parse_llm_response(response_text)
    except Exception:
        return []
