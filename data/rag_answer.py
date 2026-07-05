"""
RAG answer generation using local Ollama (free, no API key).
Requires Ollama running at OLLAMA_URL (default: http://localhost:11434).
"""
import json
import os
from typing import Dict, List, Optional

import requests

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

_SYSTEM_PROMPT = (
    "You are an expert financial analyst. Answer questions ONLY from the retrieved evidence chunks. "
    "Do NOT use prior knowledge — if evidence is insufficient note it and use a low confidence_score. "
    "Respond with valid JSON only containing exactly these keys: "
    '"answer" (string), '
    '"confidence_score" (float 0.0–1.0), '
    '"citations" (list of objects, each with: section_name, company, filing_date, filing_type, quote). '
    "No other text or formatting outside the JSON object."
)

_EMPTY_ANSWER = {"answer": "No relevant filings found.", "confidence_score": 0.0, "citations": []}
_ERROR_ANSWER = {"answer": "Error generating answer.", "confidence_score": 0.0, "citations": []}

_CITATION_KEYS = {"section_name", "company", "filing_date", "filing_type", "quote"}


def _call_ollama(user_message: str) -> Optional[str]:
    try:
        resp = requests.post(
            f"{_OLLAMA_URL}/api/chat",
            json={
                "model": _OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        return None


def _parse_llm_response(text: str):
    stripped = text.strip()
    # Strip markdown code fences
    if stripped.startswith("```"):
        lines = [l for l in stripped.splitlines() if not l.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    # Extract first {...} block if model added surrounding text
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1:
            stripped = stripped[start:end + 1]
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        # Last resort: treat entire response as plain answer
        if len(stripped) > 10:
            return {"answer": stripped, "confidence_score": 0.5, "citations": []}
        return None
    answer = data.get("answer") or data.get("response") or data.get("text")
    if not isinstance(answer, str) or not answer.strip():
        return None
    try:
        clamped_score = max(0.0, min(1.0, float(data.get("confidence_score", 0.5))))
    except (TypeError, ValueError):
        clamped_score = 0.5
    raw_citations = data.get("citations") or []
    if not isinstance(raw_citations, list):
        raw_citations = []
    # Fill in missing citation keys rather than rejecting
    citations = []
    for c in raw_citations:
        if isinstance(c, dict):
            citations.append({k: c.get(k, "") for k in _CITATION_KEYS})
    return {"answer": answer, "confidence_score": clamped_score, "citations": citations}


def answer_from_chunks(question: str, chunks: List[Dict]) -> Dict:
    """Generate a grounded answer from retrieved evidence chunks using Ollama. Never raises."""
    if not chunks:
        return _EMPTY_ANSWER.copy()
    try:
        evidence_parts = []
        for i, chunk in enumerate(chunks, start=1):
            header = (
                f"[{i}] Company: {chunk.get('company', '')} | "
                f"Filing Date: {chunk.get('filing_date', '')} | "
                f"Filing Type: {chunk.get('filing_type', '')} | "
                f"Section: {chunk.get('section_name', '')}"
            )
            evidence_parts.append(f"{header}\n{chunk.get('content', '')}")
        user_message = (
            f"Question: {question}\n\nEvidence chunks:\n\n" + "\n\n".join(evidence_parts)
        )
        response_text = _call_ollama(user_message)
        if response_text is None:
            return _ERROR_ANSWER.copy()
        result = _parse_llm_response(response_text)
        return result if result is not None else _ERROR_ANSWER.copy()
    except Exception:
        return _ERROR_ANSWER.copy()
