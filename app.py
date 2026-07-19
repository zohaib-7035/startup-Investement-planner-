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
import logging

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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    today = datetime.date.today().isoformat()
    return render_template("index.html", today=today)


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


# ── VC Brain routes ───────────────────────────────────────────────────────────

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
        # TODO Story 2 — founder_data.py not yet implemented
        return jsonify({"status": "not implemented"}), 501
    except Exception as e:
        log.error("source: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/score", methods=["POST"])
def score():
    """Run three-axis scoring (Founder / Market / Idea-vs-Market) for a founder profile."""
    body = request.get_json(silent=True) or {}
    if "profile" not in body:
        return jsonify({"error": "provide 'profile' key with a FounderProfile object"}), 400

    try:
        from data.founder_data import FounderProfile
        from data.founder_signals import generate_founder_signals
        from data.thesis_engine import ThesisConfig, evaluate_founder
        from data.risk_flags import flag_risks
        from data.decision_engine import (
            compute_founder_axis, compute_market_axis, compute_idea_axis, make_decision
        )
        from data.parallel_runner import run_agents_parallel

        profile = FounderProfile(**body["profile"])
        thesis_config_data = body.get("thesis_config")
        thesis_config = ThesisConfig(**thesis_config_data) if thesis_config_data else ThesisConfig()

        agent_dispatch = {
            "signals":      (generate_founder_signals, [profile], {}),
            "thesis":       (evaluate_founder, [profile, thesis_config], {}),
            "founder_axis": (compute_founder_axis, [profile], {}),
            "market_axis":  (compute_market_axis, [profile], {}),
            "idea_axis":    (compute_idea_axis, [profile], {}),
        }
        results = run_agents_parallel(agent_dispatch)

        signals       = results.get("signals", {})
        thesis_result = results.get("thesis", None)
        risk_flags    = flag_risks(profile, signals)
        decision      = make_decision(
            results.get("founder_axis"),
            results.get("market_axis"),
            results.get("idea_axis"),
            thesis_result,
            risk_flags,
        )

        return jsonify({
            "signals":      signals,
            "thesis_result": dataclasses.asdict(thesis_result) if thesis_result else None,
            "risk_flags":   [dataclasses.asdict(f) for f in risk_flags],
            "decision":     dataclasses.asdict(decision),
        })
    except ImportError:
        # TODO Story 3 — scoring modules not yet implemented
        return jsonify({"status": "not implemented"}), 501
    except Exception as e:
        log.error("score: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/memo", methods=["POST"])
def memo():
    """Generate an Investment Memo from a scored founder profile."""
    body = request.get_json(silent=True) or {}
    required = ("profile", "thesis_result", "risk_flags", "decision")
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify({"error": f"missing required keys: {missing}"}), 400

    try:
        from data.founder_data import FounderProfile
        from data.thesis_engine import ThesisResult
        from data.risk_flags import RiskFlag
        from data.decision_engine import DecisionResult, AxisScore
        from data.memo_generator import generate_memo

        profile       = FounderProfile(**body["profile"])
        thesis_result = ThesisResult(**body["thesis_result"]) if body["thesis_result"] else None
        risk_flags    = [RiskFlag(**f) for f in (body["risk_flags"] or [])]
        dec_data      = body["decision"]
        axes          = [AxisScore(**a) for a in dec_data.get("axes", [])]
        decision      = DecisionResult(
            axes=axes,
            overall_verdict=dec_data.get("overall_verdict", ""),
            memo_inputs=dec_data.get("memo_inputs", {}),
        )

        investment_memo = generate_memo(profile, thesis_result, risk_flags, decision)
        return jsonify(dataclasses.asdict(investment_memo))
    except ImportError:
        # TODO Story 4 — memo_generator.py not yet implemented
        return jsonify({"status": "not implemented"}), 501
    except Exception as e:
        log.error("memo: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    ollama_ok = _check_ollama()
    vader_ok  = _check_vader()
    model     = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    port      = int(os.environ.get("FLASK_PORT", 5000))
    host      = os.environ.get("FLASK_HOST", "0.0.0.0")
    debug     = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    print("\n" + "=" * 65)
    print("  VC Brain — Startup Investment Intelligence")
    print("=" * 65)
    print(f"  Ollama ({model}): {'OK — ready' if ollama_ok else 'NOT RUNNING — run: ollama serve'}")
    print(f"  VADER sentiment : {'OK' if vader_ok else 'MISSING — pip install vaderSentiment'}")
    print(f"  Dashboard       : http://localhost:{port}")
    print("=" * 65 + "\n")
    app.run(debug=debug, port=port, host=host)
