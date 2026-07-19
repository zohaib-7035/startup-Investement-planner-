"""
VC Brain — Flask web application.
Sources, scores, and generates investment memos for startup founders.
All data sources: GitHub REST API (free, unauthenticated), Ollama (local LLM).
"""
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import dataclasses
import datetime
import json
import logging
import pathlib

from flask import Flask, jsonify, render_template, request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("app")

app = Flask(__name__)

_THESIS_CONFIG_PATH = pathlib.Path(__file__).parent / "data" / "thesis_config.json"


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": f"Bad request: {e}"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    log.error("Unhandled 500: %s", e, exc_info=True)
    return jsonify({"error": str(e)}), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    log.error("Unhandled exception: %s", e, exc_info=True)
    return jsonify({"error": str(e)}), 500


# ── Utility helpers ───────────────────────────────────────────────────────────

def _check_ollama():
    try:
        import requests as _r
        return _r.get(os.environ.get("OLLAMA_URL", "http://localhost:11434"), timeout=2).status_code == 200
    except Exception:
        return False


def _check_vader():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # noqa
        return True
    except ImportError:
        return False


def _load_thesis_config():
    """Load ThesisConfig from disk, returning defaults if file absent or malformed."""
    from data.thesis_engine import ThesisConfig
    try:
        if _THESIS_CONFIG_PATH.exists():
            with open(_THESIS_CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            valid_fields = {fld.name for fld in dataclasses.fields(ThesisConfig)}
            return ThesisConfig(**{k: v for k, v in data.items() if k in valid_fields})
    except Exception:
        pass
    return ThesisConfig()


def _build_evidence(profile):
    """Convert founder signals + key_signals into verify_claim()-compatible evidence list."""
    from data.founder_signals import generate_founder_signals
    signals = generate_founder_signals(profile)
    evidence = [
        {"signal": name, "score": sig.get("score") or 0, "direction": sig.get("direction", "unknown")}
        for name, sig in signals.items()
        if sig.get("score") is not None
    ]
    # Add total_stars directly — sample_founders.json uses this key; verify_claim checks it
    ks = profile.key_signals or {}
    if "total_stars" in ks:
        if not any(e["signal"] == "total_stars" for e in evidence):
            evidence.append({"signal": "total_stars", "score": ks["total_stars"], "direction": "unknown"})
    return evidence


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    today = datetime.date.today().isoformat()
    one_year_ago = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    return render_template("index.html", today=today, one_year_ago=one_year_ago)


@app.route("/api/status")
def status():
    return jsonify({
        "vader":        _check_vader(),
        "ollama":       _check_ollama(),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
    })


@app.route("/api/knowledge-graph", methods=["POST"])
def knowledge_graph_route():
    """
    Extract entity relationships from text using Ollama, then optionally
    run BFS impact analysis for a disrupted entity.
    Body: {text: str, disrupted_entity: str (optional)}
    """
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", "")).strip()
    disrupted_entity = str(body.get("disrupted_entity", "")).strip()
    if not text:
        return jsonify({"error": "text is required."}), 400
    log.info("Knowledge graph: %d chars, entity=%s", len(text), disrupted_entity or "(none)")
    try:
        from data.knowledge_graph import extract_relationships
        from data.graph_reasoning import analyze_impact
        triples = extract_relationships(text)
        impact = {}
        if disrupted_entity:
            impact = analyze_impact(triples, disrupted_entity)
        return jsonify({"triples": triples, "triple_count": len(triples), "impact": impact})
    except Exception as e:
        log.error("knowledge graph: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ── VC Brain API routes ───────────────────────────────────────────────────────

@app.route("/api/founders", methods=["GET"])
def api_founders():
    """Return all sample founders as a JSON list with their array index as founder_id."""
    try:
        from data.sourcing import load_sample_founders
        founders = load_sample_founders()
        result = []
        for idx, profile in enumerate(founders):
            ks = profile.key_signals or {}
            result.append({
                "founder_id": idx,
                "name":    profile.name or "",
                "company": profile.company or "",
                "sector":  profile.sector or "",
                "stage":   profile.stage or "",
                "source":  ks.get("source", "inbound"),
            })
        return jsonify(result)
    except Exception as e:
        log.error("api_founders: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/screen/<int:idx>", methods=["POST"])
def api_screen(idx):
    """
    Run the full VC Brain pipeline for the founder at position idx in sample_founders.json.
    Returns: { screening, memo, reasoning_log, profile }
    """
    try:
        from data.sourcing import load_sample_founders
        founders = load_sample_founders()
        if idx < 0 or idx >= len(founders):
            return jsonify({"error": f"Founder index {idx} out of range (0–{len(founders)-1})"}), 404

        profile = founders[idx]
        thesis_config = _load_thesis_config()

        from data.scoring_engine import run_full_screening
        screening = run_full_screening(profile, thesis_config)

        from data.trust_score import extract_claims, verify_claim
        claims = extract_claims(profile)
        evidence = _build_evidence(profile)
        verified_claims = [verify_claim(c, evidence) for c in claims]

        from data.memo_generator import generate_memo
        memo = generate_memo(profile, screening, verified_claims)

        from data.reasoning_log import build_screening_log
        reasoning_log = build_screening_log(profile, screening, verified_claims, idx)

        return jsonify({
            "screening":     dataclasses.asdict(screening),
            "memo":          dataclasses.asdict(memo),
            "reasoning_log": dataclasses.asdict(reasoning_log),
            "profile": {
                "name":    profile.name or "",
                "company": profile.company or "",
                "sector":  profile.sector or "",
                "stage":   profile.stage or "",
                "source":  (profile.key_signals or {}).get("source", "inbound"),
            },
        })

    except Exception as e:
        log.error("api_screen idx=%s: %s", idx, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/thesis", methods=["GET"])
def api_thesis_get():
    """Return current ThesisConfig (defaults if file absent)."""
    try:
        config = _load_thesis_config()
        return jsonify(dataclasses.asdict(config))
    except Exception as e:
        log.error("api_thesis GET: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/thesis", methods=["POST"])
def api_thesis_post():
    """Validate and persist ThesisConfig to data/thesis_config.json."""
    from data.thesis_engine import ThesisConfig
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    valid_fields = {fld.name for fld in dataclasses.fields(ThesisConfig)}
    unknown = set(body) - valid_fields
    if unknown:
        return jsonify({"error": f"Unknown fields: {sorted(unknown)}"}), 400

    numeric_fields = {"check_size_min", "check_size_max", "min_ownership_pct"}
    for fld in numeric_fields:
        if fld in body and not isinstance(body[fld], (int, float)):
            return jsonify({"error": f"Field '{fld}' must be numeric"}), 400

    try:
        config = ThesisConfig(**{k: v for k, v in body.items() if k in valid_fields})
        _THESIS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_THESIS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(config), f, indent=2)
        log.info("Thesis config saved to %s", _THESIS_CONFIG_PATH)
        return jsonify(dataclasses.asdict(config))
    except Exception as e:
        log.error("api_thesis POST: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/query", methods=["POST"])
def api_query():
    """
    Natural-language multi-attribute founder search.
    Body: { "query": "technical founder, AI infra, enterprise traction" }
    Screens all founders with fast rule-based scoring, then filters via Ollama NL query.
    """
    body = request.get_json(silent=True) or {}
    q = str(body.get("query", "")).strip()
    if not q:
        return jsonify({"error": "query field is required"}), 400
    try:
        from data.sourcing import load_sample_founders
        from data.scoring_engine import (
            ScreeningResult, score_founder_axis, score_market_axis,
            _idea_vs_market_rule_based, query_founders,
        )
        from data.founder_signals import generate_founder_signals
        from data.risk_flags import flag_risks
        from data.thesis_engine import evaluate_founder

        founders = load_sample_founders()
        thesis = _load_thesis_config()

        screened = []
        for profile in founders:
            signals = generate_founder_signals(profile)
            fa = score_founder_axis(profile)
            ma = score_market_axis(profile)
            ima = _idea_vs_market_rule_based(profile)
            rf = flag_risks(profile, signals)
            tr = evaluate_founder(profile, thesis)
            if tr.verdict == "PASS":
                thesis_match, thesis_reason = True, "Matched: " + ", ".join(tr.matched_rules)
            elif tr.verdict == "WATCHLIST":
                thesis_match, thesis_reason = True, "No thesis constraints active"
            else:
                thesis_match, thesis_reason = False, "Failed: " + ", ".join(tr.failed_rules)
            screened.append(ScreeningResult(
                profile=profile,
                founder_axis=fa,
                market_axis=ma,
                idea_vs_market_axis=ima,
                risk_flags=rf,
                thesis_match=thesis_match,
                thesis_reason=thesis_reason,
            ))

        matched = query_founders(q, screened)
        matched_companies = {sr.profile.company for sr in matched}

        result = []
        for idx, profile in enumerate(founders):
            if profile.company in matched_companies:
                ks = profile.key_signals or {}
                result.append({
                    "founder_id": idx,
                    "name":    profile.name or "",
                    "company": profile.company or "",
                    "sector":  profile.sector or "",
                    "stage":   profile.stage or "",
                    "source":  ks.get("source", "inbound"),
                })
        return jsonify(result)
    except Exception as e:
        log.error("api_query: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ── Legacy VC Brain routes (deprecated — use /api/screen/<idx>) ───────────────

@app.route("/source", methods=["POST"])
def source():
    """Source founder/company data from GitHub or a pitch deck."""
    body = request.get_json(silent=True) or {}
    if "github" not in body and "pitch_deck" not in body:
        return jsonify({"error": "provide 'github' or 'pitch_deck' key"}), 400

    try:
        from data.founder_data import fetch_github_profile, ingest_pitch_deck
        if "github" in body:
            profile = fetch_github_profile(str(body["github"]).strip())
        else:
            profile = ingest_pitch_deck(str(body["pitch_deck"]).strip())
        return jsonify(dataclasses.asdict(profile))
    except ImportError:
        return jsonify({"status": "not implemented"}), 501
    except Exception as e:
        log.error("source: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/score", methods=["POST"])
def score():
    """DEPRECATED — use POST /api/screen/<idx> instead."""
    log.warning("/score is deprecated — callers should use POST /api/screen/<idx>")
    return jsonify({
        "error": "This endpoint is deprecated. Use POST /api/screen/<idx> for the full VC Brain screening pipeline.",
        "docs": "POST /api/screen/<founder_index> — returns screening, memo, reasoning_log, and profile in one call.",
    }), 410


@app.route("/memo", methods=["POST"])
def memo():
    """DEPRECATED — use POST /api/screen/<idx> instead."""
    log.warning("/memo is deprecated — callers should use POST /api/screen/<idx>")
    return jsonify({
        "error": "This endpoint is deprecated. Use POST /api/screen/<idx> for the full VC Brain pipeline including memo generation.",
        "docs": "POST /api/screen/<founder_index> — returns screening, memo, reasoning_log, and profile in one call.",
    }), 410


if __name__ == "__main__":
    ollama_ok = _check_ollama()
    vader_ok  = _check_vader()
    model     = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    port      = int(os.environ.get("FLASK_PORT", 5000))
    host      = os.environ.get("FLASK_HOST", "0.0.0.0")
    debug     = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    print("\n" + "=" * 65)
    print("  VC Brain — Agentic Founder Intelligence")
    print("=" * 65)
    print(f"  Ollama ({model}): {'OK — ready' if ollama_ok else 'NOT RUNNING — run: ollama serve'}")
    print(f"  VADER sentiment : {'OK' if vader_ok else 'MISSING — pip install vaderSentiment'}")
    print(f"  Dashboard       : http://localhost:{port}")
    print("=" * 65 + "\n")
    app.run(debug=debug, port=port, host=host)
