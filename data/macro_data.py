"""
Free macroeconomic indicators — two data sources:

1. Yahoo Finance (no key required):
   Treasury yields: ^TNX (10Y), ^TYX (30Y), ^FVX (5Y), ^IRX (13W T-Bill)
   Yield curve: 10Y − 13W spread (computed from yfinance, always available)

2. Official FRED API (free key, optional):
   Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html
   Set  FRED_API_KEY=your_key  in the .env file in the project root.
   Unlocks: Fed Funds Rate, CPI, Unemployment, GDP Growth, 2Y Treasury
"""
import datetime
import os
from typing import Dict, List, Optional

import requests
import yfinance as yf

_FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT = 10

# ── Treasury yields via Yahoo Finance (free, no key) ─────────────────────────
_YF_TREASURY: Dict[str, tuple] = {
    "10y_treasury": ("^TNX", "10-Year Treasury Yield"),
    "30y_treasury": ("^TYX", "30-Year Treasury Yield"),
    "5y_treasury":  ("^FVX",  "5-Year Treasury Yield"),
    "13w_tbill":    ("^IRX",  "13-Week T-Bill Rate"),
}

# ── Economic indicators via FRED API (free key required) ─────────────────────
_FRED_INDICATORS: Dict[str, tuple] = {
    "fed_funds_rate":    ("FEDFUNDS",        "Federal Funds Rate"),
    "cpi_yoy":           ("CPIAUCSL",        "CPI Index (All Urban)"),
    "unemployment_rate": ("UNRATE",          "Unemployment Rate"),
    "gdp_growth":        ("A191RL1Q225SBEA", "Real GDP Growth Rate"),
    "2y_treasury":       ("GS2",             "2-Year Treasury Yield"),
}


def _fetch_yf_latest(symbol: str) -> Optional[Dict]:
    """Fetch latest price and date from Yahoo Finance. Never raises."""
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="5d", interval="1d")
        if df is None or df.empty:
            return None
        closes = df["Close"].dropna()
        if closes.empty:
            return None
        return {
            "value": round(float(closes.iloc[-1]), 3),
            "date":  closes.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception:
        return None


def _fetch_fred_latest(series_id: str, api_key: str) -> Optional[Dict]:
    """Fetch the most recent FRED observation. Requires a free API key."""
    try:
        r = requests.get(
            _FRED_API_BASE,
            params={
                "series_id": series_id,
                "api_key":   api_key,
                "sort_order": "desc",
                "limit":     1,
                "file_type": "json",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if not obs:
            return None
        val_str = obs[0].get("value", ".")
        if val_str in ("", ".", None):
            return None
        return {
            "value": round(float(val_str), 4),
            "date":  obs[0].get("date", ""),
        }
    except Exception:
        return None


def _fetch_fred_series(series_id: str, limit: int = 2) -> Optional[List[Dict]]:
    """
    Fetch the last `limit` FRED observations.
    Returns None if FRED_API_KEY is not set or the request fails.
    Used by get_yield_curve_signal as a FRED fallback.
    """
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        r = requests.get(
            _FRED_API_BASE,
            params={
                "series_id": series_id,
                "api_key":   api_key,
                "sort_order": "asc",
                "limit":     limit,
                "file_type": "json",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if not obs:
            return None
        result = []
        for o in obs[-limit:]:
            val_str = o.get("value", ".")
            val = float(val_str) if val_str not in ("", ".", None) else None
            result.append({"date": o.get("date", ""), "value": val})
        return result if result else None
    except Exception:
        return None


def get_macro_indicators() -> Dict:
    """
    Return macro indicators. Structure: {key: {value, date, description, series_id}}.

    Treasury yields (^TNX, ^TYX, ^FVX, ^IRX) are always fetched from Yahoo Finance.
    Economic indicators (fed_funds_rate, cpi, unemployment, gdp, 2y) require
    FRED_API_KEY in the environment — set it in .env for full data.

    Always returns exactly 7 top-level indicator keys (no internal keys).
    Also returns _has_fred_key for the UI to show a helpful note.
    """
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    result: Dict = {}

    # Treasury yields — always available
    for key, (symbol, desc) in _YF_TREASURY.items():
        data = _fetch_yf_latest(symbol)
        result[key] = {
            "value":       data["value"] if data else None,
            "date":        data["date"]  if data else None,
            "description": desc + " (%)",
            "series_id":   symbol,
        }

    # Economic indicators — need FRED key
    for key, (series_id, desc) in _FRED_INDICATORS.items():
        data = _fetch_fred_latest(series_id, api_key) if api_key else None
        result[key] = {
            "value":       data["value"] if data else None,
            "date":        data["date"]  if data else None,
            "description": desc + " (%)",
            "series_id":   series_id,
        }

    result["_has_fred_key"] = bool(api_key)
    return result


def get_yield_curve_signal() -> Dict:
    """
    Yield curve signal from Yahoo Finance (no API key required).
    Uses 10-Year (^TNX) minus 13-Week T-Bill (^IRX) spread.
    Returns {signal, spread, date, source}.
    """
    tnx = _fetch_yf_latest("^TNX")
    irx = _fetch_yf_latest("^IRX")

    if not tnx or not irx or tnx["value"] is None or irx["value"] is None:
        return {"signal": "UNKNOWN", "spread": None, "date": None}

    spread = round(tnx["value"] - irx["value"], 3)

    if spread < 0:
        signal = "INVERTED"
    elif spread < 0.5:
        signal = "FLAT"
    else:
        signal = "NORMAL"

    return {"signal": signal, "spread": spread, "date": tnx["date"]}
