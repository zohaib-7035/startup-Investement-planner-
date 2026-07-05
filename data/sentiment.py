"""
Financial news sentiment analysis using VADER (Valence Aware Dictionary and sEntiment Reasoner).
Offline — no API key, no internet connection, no cost.
Install: pip install vaderSentiment
"""
_EMPTY_INPUT_FALLBACK = {"sentiment": "Neutral", "score": 0, "reason": "No news text provided."}
_UNAVAILABLE_FALLBACK = {"sentiment": "Neutral", "score": 0, "reason": "Sentiment analysis unavailable."}

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as _Analyzer
    _analyzer = _Analyzer()
    _VADER_OK = True
except ImportError:
    _VADER_OK = False


def analyze_sentiment(news_text) -> dict:
    """
    Classify financial news text as Positive / Neutral / Negative using VADER.
    Returns dict with keys: sentiment, score (+1/0/-1), reason. Never raises.
    """
    if news_text is None or not str(news_text).strip():
        return _EMPTY_INPUT_FALLBACK.copy()
    if not _VADER_OK:
        return _UNAVAILABLE_FALLBACK.copy()
    try:
        compound = _analyzer.polarity_scores(str(news_text))["compound"]
        if compound >= 0.05:
            return {
                "sentiment": "Positive",
                "score": 1,
                "reason": f"Positive tone detected in market news (VADER score: {compound:.2f}).",
            }
        if compound <= -0.05:
            return {
                "sentiment": "Negative",
                "score": -1,
                "reason": f"Negative tone detected in market news (VADER score: {compound:.2f}).",
            }
        return {
            "sentiment": "Neutral",
            "score": 0,
            "reason": f"Neutral tone detected in market news (VADER score: {compound:.2f}).",
        }
    except Exception:
        return _UNAVAILABLE_FALLBACK.copy()
