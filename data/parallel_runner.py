import concurrent.futures

import numpy as np
import yfinance as yf

from data.stock import get_stock_history, get_fundamentals
from data.screener import generate_recommendation
from data.sentiment import analyze_sentiment
from data.risk import calculate_risk_metrics
from data.meta_agent import aggregate_signals

_EMPTY_RESULT = {
    "final_action": "HOLD",
    "confidence": 0.0,
    "reasoning": "",
    "conflicts": [],
}

_TECHNICAL_FALLBACK = {"action": "HOLD", "confidence": 0.0}
_FUNDAMENTALS_FALLBACK = {"action": "HOLD", "confidence": 0.0}
_SENTIMENT_FALLBACK = {"action": "HOLD", "confidence": 0.0}
_MACRO_FALLBACK = {"action": "HOLD", "confidence": 0.0}
_RISK_FALLBACK = {"level": "LOW"}
_NEWS_FALLBACK = ""

_SCORE_TO_ACTION = {1: "BUY", 0: "HOLD", -1: "SELL"}
_SENTIMENT_CONFIDENCE = {"Positive": 0.75, "Neutral": 0.50, "Negative": 0.75}


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
        rs = avg_gain / avg_loss
        return float(100.0 - 100.0 / (1.0 + rs))
    except Exception:
        return None


def _run_news_agent(ticker):
    """Fetch recent news headlines from Yahoo Finance and join into a text blob."""
    try:
        raw = yf.Ticker(ticker).news or []
        titles = []
        for item in raw[:8]:
            content = item.get("content") or item
            title = content.get("title", "") or ""
            if title.strip():
                titles.append(title.strip())
        return " ".join(titles) if titles else _NEWS_FALLBACK
    except Exception:
        return _NEWS_FALLBACK


def _run_macro_agent(ticker):
    try:
        return _MACRO_FALLBACK.copy()
    except Exception:
        return _MACRO_FALLBACK.copy()


def _run_technical_agent(ticker, start, end):
    try:
        history = get_stock_history(ticker, start, end)
        if not history:
            return _TECHNICAL_FALLBACK.copy()
        close_prices = [row["close"] for row in history]
        rsi = _compute_rsi(close_prices)
        fundamentals = get_fundamentals(ticker)
        eps_surprise = fundamentals.get("eps_surprise")
        pe_ratio = fundamentals.get("pe_ratio")
        result = generate_recommendation(rsi, eps_surprise, pe_ratio)
        action = str(result.get("action", "HOLD")).upper()
        confidence = float(result.get("confidence", 0.0))
        return {"action": action, "confidence": confidence}
    except Exception:
        return _TECHNICAL_FALLBACK.copy()


def _run_fundamentals_agent(ticker):
    try:
        fundamentals = get_fundamentals(ticker)
        eps_surprise = fundamentals.get("eps_surprise")
        try:
            eps_val = float(eps_surprise) if eps_surprise is not None else None
        except (TypeError, ValueError):
            eps_val = None
        if eps_val is not None and eps_val > 0:
            action = "BUY"
        elif eps_val is not None and eps_val < 0:
            action = "SELL"
        else:
            action = "HOLD"
        confidence = 0.70 if eps_val is not None else 0.0
        return {"action": action, "confidence": float(confidence)}
    except Exception:
        return _FUNDAMENTALS_FALLBACK.copy()


def _run_sentiment_agent(news_texts):
    try:
        if not news_texts or not news_texts.strip():
            return _SENTIMENT_FALLBACK.copy()
        result = analyze_sentiment(news_texts)
        score = result.get("score", 0)
        sentiment = result.get("sentiment", "Neutral")
        action = _SCORE_TO_ACTION.get(score, "HOLD")
        confidence = _SENTIMENT_CONFIDENCE.get(sentiment, 0.50)
        return {"action": action, "confidence": float(confidence)}
    except Exception:
        return _SENTIMENT_FALLBACK.copy()


def _run_risk_agent(ticker, start, end):
    try:
        history = get_stock_history(ticker, start, end)
        if not history:
            return _RISK_FALLBACK.copy()
        metrics = calculate_risk_metrics(
            weights={ticker: 1.0},
            returns_data={ticker: history},
        )
        risk_level = metrics.get("risk_level")
        return {"level": risk_level or "LOW"}
    except Exception:
        return _RISK_FALLBACK.copy()


def run_agents_parallel(
    ticker,
    start,
    end,
    news_texts=None,
    timeout_seconds=30,
    max_retries=2,
):
    try:
        try:
            ts = float(timeout_seconds)
        except (TypeError, ValueError):
            return _EMPTY_RESULT.copy()
        if ts <= 0:
            return _EMPTY_RESULT.copy()

        # Phase 1: determine effective news text
        if news_texts is not None:
            effective_news = news_texts
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as news_executor:
                try:
                    f = news_executor.submit(_run_news_agent, ticker)
                    effective_news = f.result(timeout=ts)
                except Exception:
                    effective_news = _NEWS_FALLBACK

        # Phase 2: run 5 main agents in parallel with per-agent retry
        agent_dispatch = {
            "technical": (_run_technical_agent, [ticker, start, end]),
            "fundamentals": (_run_fundamentals_agent, [ticker]),
            "sentiment": (_run_sentiment_agent, [effective_news]),
            "macro": (_run_macro_agent, [ticker]),
            "risk": (_run_risk_agent, [ticker, start, end]),
        }
        _fallbacks = {
            "technical": _TECHNICAL_FALLBACK,
            "fundamentals": _FUNDAMENTALS_FALLBACK,
            "sentiment": _SENTIMENT_FALLBACK,
            "macro": _MACRO_FALLBACK,
            "risk": _RISK_FALLBACK,
        }

        results = {}
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        try:
            for _attempt in range(int(max_retries) + 1):
                unresolved = {
                    name: agent_dispatch[name]
                    for name in agent_dispatch
                    if name not in results
                }
                if not unresolved:
                    break
                pending = {
                    name: executor.submit(fn, *args)
                    for name, (fn, args) in unresolved.items()
                }
                for name, future in pending.items():
                    try:
                        results[name] = future.result(timeout=ts)
                    except Exception:
                        future.cancel()
        finally:
            executor.shutdown(wait=False)

        for name in agent_dispatch:
            if name not in results:
                fb = _fallbacks[name]
                results[name] = fb.copy() if isinstance(fb, dict) else fb

        agent_outputs = {
            "technical": results["technical"],
            "fundamentals": results["fundamentals"],
            "sentiment": results["sentiment"],
            "macro": results["macro"],
            "risk": results["risk"],
        }
        return aggregate_signals(agent_outputs)

    except Exception:
        return _EMPTY_RESULT.copy()
