"""
AI Stock Intelligence Platform — Flask web application.
All data sources: yfinance (free), SEC EDGAR (free), FRED (free), Ollama (local LLM).
No paid APIs required.
"""
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import concurrent.futures
import datetime
import logging
import re

import numpy as np
import yfinance as yf
from flask import Flask, jsonify, render_template, request

# Load .env if present (python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data.meta_agent import aggregate_signals
from data.notifier import send_alert
from data.portfolio import optimize_portfolio
from data.risk import calculate_risk_metrics
from data.scenario import simulate_scenario
from data.screener import generate_recommendation
from data.sentiment import analyze_sentiment
from data.signals import generate_advanced_signal
from data.stock import get_fundamentals, get_stock_history

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("app")

app = Flask(__name__)

# ── Global JSON error handlers ────────────────────────────────────────────────
# Flask returns HTML by default for unhandled errors. These ensure JSON always.

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

# In-memory alert history (last 100 alerts)
_alert_history: list = []
_MAX_ALERT_HISTORY = 100


# ── Technical indicator helpers ──────────────────────────────────────────────

def _compute_rsi(close_prices, period=14):
    try:
        if len(close_prices) <= period:
            return None
        prices = np.array(close_prices, dtype=float)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0.0:
            return 100.0
        return float(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    except Exception:
        return None


def _compute_atr(history, period=14):
    try:
        if len(history) <= period:
            return None
        trs = []
        for i in range(1, len(history)):
            h, l, pc = history[i]["high"], history[i]["low"], history[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return float(np.mean(trs[-period:])) if len(trs) >= period else None
    except Exception:
        return None


def _compute_adx(history, period=14):
    try:
        if len(history) <= period * 2:
            return None
        highs = [r["high"] for r in history]
        lows = [r["low"] for r in history]
        closes = [r["close"] for r in history]
        plus_dm, minus_dm, trs = [], [], []
        for i in range(1, len(history)):
            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]
            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)
            trs.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            ))
        atr_s = float(np.mean(trs[:period]))
        p_s = float(np.mean(plus_dm[:period]))
        m_s = float(np.mean(minus_dm[:period]))
        for i in range(period, len(trs)):
            atr_s = (atr_s * (period - 1) + trs[i]) / period
            p_s = (p_s * (period - 1) + plus_dm[i]) / period
            m_s = (m_s * (period - 1) + minus_dm[i]) / period
        if atr_s == 0:
            return None
        plus_di = 100 * p_s / atr_s
        minus_di = 100 * m_s / atr_s
        di_sum = plus_di + minus_di
        return float(100 * abs(plus_di - minus_di) / di_sum) if di_sum > 0 else 0.0
    except Exception:
        return None


def _compute_momentum(close_prices, period=14):
    try:
        if len(close_prices) < period + 1:
            return None
        return float(close_prices[-1] - close_prices[-period - 1])
    except Exception:
        return None


def _compute_volume_ratio(history, short=5, long=20):
    try:
        if len(history) < long:
            return None
        vols = [r["volume"] for r in history]
        la = float(np.mean(vols[-long:]))
        return float(np.mean(vols[-short:]) / la) if la > 0 else None
    except Exception:
        return None


def _fmt_market_cap(val):
    try:
        v = float(val)
        if v >= 1e12:
            return f"${v / 1e12:.2f}T"
        if v >= 1e9:
            return f"${v / 1e9:.2f}B"
        if v >= 1e6:
            return f"${v / 1e6:.2f}M"
        return f"${v:,.0f}"
    except Exception:
        return None


def _safe_float(val, ndigits=2):
    try:
        return round(float(val), ndigits)
    except (TypeError, ValueError):
        return None


def _fetch_news(ticker_symbol):
    try:
        raw = yf.Ticker(ticker_symbol).news or []
        result = []
        for item in raw[:6]:
            content = item.get("content") or item
            title = content.get("title", "") or ""
            if not title.strip():
                continue
            provider = content.get("provider") or {}
            publisher = provider.get("displayName", "") or content.get("publisher", "")
            click_url = content.get("clickThroughUrl") or {}
            link = click_url.get("url", "") or content.get("link", "")
            result.append({"title": title, "publisher": publisher, "link": link})
            if len(result) == 5:
                break
        return result
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    today = datetime.date.today().isoformat()
    one_year_ago = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    return render_template("index.html", today=today, one_year_ago=one_year_ago)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    body = request.get_json(silent=True) or {}
    ticker = str(body.get("ticker", "")).strip().upper()
    start = body.get("start") or (
        datetime.date.today() - datetime.timedelta(days=365)
    ).isoformat()
    end = body.get("end") or datetime.date.today().isoformat()

    if not ticker:
        return jsonify({"error": "Ticker symbol is required."}), 400
    if not re.match(r"^[A-Z0-9.\^\-]{1,10}$", ticker):
        return jsonify({"error": "Invalid ticker format. Use letters, digits, . ^ - only (max 10 chars)."}), 400

    log.info("Analyzing %s (%s → %s)", ticker, start, end)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            history_f = ex.submit(get_stock_history, ticker, start, end)
            fund_f    = ex.submit(get_fundamentals, ticker)
            info_f    = ex.submit(lambda: yf.Ticker(ticker).info or {})
            news_f    = ex.submit(_fetch_news, ticker)

        history        = history_f.result()
        fundamentals   = fund_f.result()
        info           = info_f.result()
        news_headlines = news_f.result()

        news_text = " ".join(n["title"] for n in news_headlines)

        close_prices = [r["close"] for r in history if r.get("close") is not None]
        rsi          = _compute_rsi(close_prices)
        atr          = _compute_atr(history)
        adx          = _compute_adx(history)
        momentum     = _compute_momentum(close_prices)
        volume_ratio = _compute_volume_ratio(history)

        eps_surprise = _safe_float(fundamentals.get("eps_surprise"), 4)
        pe_ratio     = _safe_float(fundamentals.get("pe_ratio"))

        # Agent 1 — Technical
        tech        = generate_recommendation(rsi, eps_surprise, pe_ratio)
        tech_action = str(tech.get("action", "HOLD")).upper()
        tech_conf   = max(0.0, min(1.0, float(tech.get("confidence", 0.0))))
        tech_reason = tech.get("reason", "")

        # Agent 2 — Advanced Signals
        sig              = generate_advanced_signal(adx, atr, momentum, volume_ratio)
        sig_action_display = str(sig.get("action", "HOLD"))
        sig_action_agg   = sig_action_display if sig_action_display in ("BUY", "SELL", "HOLD") else "HOLD"
        sig_conf         = max(0.0, min(1.0, float(sig.get("confidence", 0.0))))
        sig_reason       = sig.get("reason", "")

        # Agent 3 — Fundamentals
        if eps_surprise is not None and eps_surprise > 0:
            fund_action, fund_conf = "BUY", 0.70
        elif eps_surprise is not None and eps_surprise < 0:
            fund_action, fund_conf = "SELL", 0.70
        else:
            fund_action, fund_conf = "HOLD", 0.50

        # Agent 4 — Sentiment
        sent_result    = analyze_sentiment(news_text) if news_text else {
            "sentiment": "Neutral", "score": 0, "reason": "No news headlines found."
        }
        sentiment_label = sent_result.get("sentiment", "Neutral")
        sent_action     = {1: "BUY", 0: "HOLD", -1: "SELL"}.get(sent_result.get("score", 0), "HOLD")
        sent_conf       = {"Positive": 0.75, "Neutral": 0.50, "Negative": 0.75}.get(sentiment_label, 0.50)
        sent_reason     = sent_result.get("reason", "")

        # Agent 5 — Macro (yield curve signal via yfinance — no API key needed)
        macro_reason = "Macro module — default neutral stance."
        try:
            from data.macro_data import get_yield_curve_signal as _gycs
            _yc = _gycs()
            _yc_sig = (_yc.get("signal") or "UNKNOWN").upper()
            _spread = _yc.get("spread")
            if _yc_sig == "INVERTED":
                macro_action, macro_conf = "SELL", 0.65
                macro_reason = f"Yield curve INVERTED (10Y-3M spread: {_spread}%). Recession risk elevated."
            elif _yc_sig == "NORMAL":
                macro_action, macro_conf = "HOLD", 0.55
                macro_reason = f"Yield curve NORMAL (10Y-3M spread: {_spread}%). Healthy growth signal."
            else:
                macro_action, macro_conf = "HOLD", 0.40
                macro_reason = f"Yield curve {_yc_sig} (10Y-3M spread: {_spread}%)."
        except Exception:
            macro_action, macro_conf = "HOLD", 0.40

        # Agent 6 — Risk
        risk_level    = "MEDIUM"
        var_val       = None
        portfolio_vol = None
        if history:
            risk        = calculate_risk_metrics(weights={ticker: 1.0}, returns_data={ticker: history})
            risk_level  = (risk.get("risk_level") or "MEDIUM").upper()
            var_val     = _safe_float(risk.get("var_1w_95"), 4)
            portfolio_vol = _safe_float(risk.get("portfolio_volatility"), 4)

        # Aggregate
        final = aggregate_signals({
            "technical":    {"action": tech_action,    "confidence": tech_conf},
            "signals":      {"action": sig_action_agg, "confidence": sig_conf},
            "fundamentals": {"action": fund_action,    "confidence": fund_conf},
            "sentiment":    {"action": sent_action,    "confidence": sent_conf},
            "macro":        {"action": macro_action,   "confidence": macro_conf},
            "risk":         {"level": risk_level},
        })

        # Price
        latest_price    = close_prices[-1] if close_prices else None
        prev_price      = close_prices[-2] if len(close_prices) >= 2 else None
        price_change_pct = None
        if latest_price and prev_price and prev_price != 0:
            price_change_pct = round(((latest_price - prev_price) / prev_price) * 100, 2)

        log.info("%s → %s %.0f%%", ticker, final.get("final_action"), float(final.get("confidence", 0)) * 100)

        return jsonify({
            "ticker":       ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "sector":       info.get("sector", ""),
            "industry":     info.get("industry", ""),
            "action":       final.get("final_action", "HOLD"),
            "confidence":   round(float(final.get("confidence", 0.0)) * 100),
            "reasoning":    final.get("reasoning", ""),
            "conflicts":    final.get("conflicts", []),
            "agents": {
                "technical": {
                    "action":     tech_action,
                    "confidence": round(tech_conf * 100),
                    "reason":     tech_reason,
                    "rsi":        round(rsi, 1) if rsi is not None else None,
                },
                "signals": {
                    "action":       sig_action_display,
                    "confidence":   round(sig_conf * 100),
                    "reason":       sig_reason,
                    "adx":          round(adx, 1) if adx is not None else None,
                    "atr":          round(atr, 2) if atr is not None else None,
                    "momentum":     round(momentum, 2) if momentum is not None else None,
                    "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
                },
                "fundamentals": {
                    "action":      fund_action,
                    "confidence":  round(fund_conf * 100),
                    "eps_surprise":eps_surprise,
                },
                "sentiment": {
                    "action":     sent_action,
                    "confidence": round(sent_conf * 100),
                    "label":      sentiment_label,
                    "reason":     sent_reason,
                    "news_count": len(news_headlines),
                },
                "macro": {
                    "action":     macro_action,
                    "confidence": round(macro_conf * 100),
                    "reason":     macro_reason,
                },
                "risk": {
                    "level":      risk_level,
                    "var":        round(var_val * 100, 2) if var_val is not None else None,
                    "volatility": round(portfolio_vol * 100, 2) if portfolio_vol is not None else None,
                },
            },
            "fundamentals": {
                "pe_ratio":       pe_ratio,
                "pb_ratio":       _safe_float(fundamentals.get("pb_ratio")),
                "eps":            _safe_float(fundamentals.get("eps_last")),
                "eps_surprise":   eps_surprise,
                "debt_to_equity": _safe_float(fundamentals.get("debt_to_equity")),
                "market_cap":     _fmt_market_cap(info.get("marketCap")),
                "dividend_yield": _safe_float(info.get("dividendYield"), 4),
                "beta":           _safe_float(info.get("beta")),
                "week52_high":    _safe_float(info.get("fiftyTwoWeekHigh")),
                "week52_low":     _safe_float(info.get("fiftyTwoWeekLow")),
            },
            "price": {
                "latest":     round(latest_price, 2) if latest_price else None,
                "change_pct": price_change_pct,
                "currency":   info.get("currency", "USD"),
            },
            "news": news_headlines,
        })

    except Exception as e:
        log.error("analyze %s: %s", ticker, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/scenario", methods=["POST"])
def scenario():
    body  = request.get_json(silent=True) or {}
    event = str(body.get("event", "")).strip()
    if not event:
        return jsonify({"error": "Event description is required."}), 400
    log.info("Scenario simulation: %s…", event[:60])
    try:
        return jsonify(simulate_scenario(event))
    except Exception as e:
        log.error("scenario: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/optimize", methods=["POST"])
def portfolio_optimize():
    """
    Markowitz mean-variance portfolio optimization.
    Body: {tickers: ["AAPL","MSFT",...], risk_tolerance: 0.5, horizon_years: 1}
    Free: uses yfinance historical prices only.
    """
    body = request.get_json(silent=True) or {}
    tickers = body.get("tickers", [])
    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "tickers must be a non-empty list."}), 400
    risk_tolerance = body.get("risk_tolerance", 0.5)
    horizon_years  = body.get("horizon_years", 1)
    log.info("Portfolio optimize: %s tickers, risk_tol=%.2f", len(tickers), risk_tolerance)
    try:
        result = optimize_portfolio(tickers, risk_tolerance, horizon_years)
        return jsonify(result)
    except Exception as e:
        log.error("portfolio optimize: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/market", methods=["GET"])
def market_snapshot():
    """
    Return indices, sector performance, commodities, currencies.
    Free data from Yahoo Finance only.
    """
    try:
        from data.market_data import get_market_snapshot
        return jsonify(get_market_snapshot())
    except Exception as e:
        log.error("market snapshot: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/macro", methods=["GET"])
def macro_indicators():
    """
    Return macroeconomic indicators from FRED (Federal Reserve, free, no key).
    Includes: Fed funds rate, CPI, unemployment, GDP, yield curve.
    """
    try:
        from data.macro_data import get_macro_indicators, get_yield_curve_signal
        indicators = get_macro_indicators()
        yc_signal  = get_yield_curve_signal()
        return jsonify({"indicators": indicators, "yield_curve": yc_signal})
    except Exception as e:
        log.error("macro indicators: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/alert", methods=["POST"])
def send_telegram_alert():
    """
    Send a Telegram alert. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.
    Free: Telegram Bot API has no cost.
    """
    body = request.get_json(silent=True) or {}
    result = send_alert(body)
    if result.get("success"):
        _alert_history.append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "payload":   body,
            "result":    result,
        })
        if len(_alert_history) > _MAX_ALERT_HISTORY:
            _alert_history.pop(0)
    return jsonify(result)


@app.route("/api/alerts/history", methods=["GET"])
def alert_history():
    """Return the last N alerts sent (in-memory, resets on restart)."""
    limit = min(int(request.args.get("limit", 50)), _MAX_ALERT_HISTORY)
    return jsonify({"alerts": _alert_history[-limit:], "total": len(_alert_history)})


@app.route("/api/status")
def status():
    return jsonify({
        "vader":        _check_vader(),
        "ollama":       _check_ollama(),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
    })


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



@app.route("/api/backtest", methods=["POST"])
def backtest():
    """
    Run a backtest for a list of dated BUY/SELL signals against historical prices.
    Body: {ticker, start, end, signals: [{date, action}, ...], initial_capital}
    Free data via yfinance.
    """
    body = request.get_json(silent=True) or {}
    ticker = str(body.get("ticker", "")).strip().upper()
    if not ticker:
        return jsonify({"error": "ticker is required."}), 400
    signals = body.get("signals", [])
    if not isinstance(signals, list) or not signals:
        return jsonify({"error": "signals must be a non-empty list of {date, action} dicts."}), 400
    start = body.get("start") or (
        datetime.date.today() - datetime.timedelta(days=365)
    ).isoformat()
    end = body.get("end") or datetime.date.today().isoformat()
    initial_capital = float(body.get("initial_capital", 10000.0))
    try:
        from data.backtester import run_backtest
        result = run_backtest(signals, ticker, start, end, initial_capital)
        return jsonify(result)
    except Exception as e:
        log.error("backtest %s: %s", ticker, e, exc_info=True)
        return jsonify({"error": str(e)}), 500




@app.route("/api/knowledge-graph", methods=["POST"])
def knowledge_graph_route():
    """
    Extract financial entity relationships from text using Ollama, then optionally
    run BFS impact analysis for a disrupted entity.
    Body: {text: str, disrupted_entity: str (optional)}
    Free: Ollama (local LLM), networkx-style BFS (pure Python).
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


if __name__ == "__main__":
    ollama_ok = _check_ollama()
    vader_ok  = _check_vader()
    model     = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    port      = int(os.environ.get("FLASK_PORT", 5000))
    host      = os.environ.get("FLASK_HOST", "0.0.0.0")
    debug     = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    print("\n" + "=" * 65)
    print("  AI Stock Intelligence Platform")
    print("=" * 65)
    print(f"  Sentiment  (VADER)        : {'OK — offline' if vader_ok else 'MISSING — pip install vaderSentiment'}")
    print(f"  Scenario   (Ollama {model}): {'OK — ready' if ollama_ok else 'NOT RUNNING — run: ollama serve'}")
    print(f"  Dashboard  (Flask)        : http://localhost:{port}")
    print("=" * 65 + "\n")
    app.run(debug=debug, port=port, host=host)
