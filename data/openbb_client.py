"""
Company dataset retrieval using yfinance (free, no registration required).
Replaces the OpenBB SDK to eliminate paid/registration dependency.
"""
import datetime
from typing import Dict, List, Optional

import yfinance as yf

_EMPTY_DATASET = {
    "company_profile": None,
    "latest_price": None,
    "market_cap": None,
    "pe_ratio": None,
    "eps": None,
    "revenue_growth": None,
    "sector": None,
    "industry": None,
    "analyst_recommendations": None,
}


def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _parse_recommendations(ticker_obj) -> Optional[List[Dict]]:
    try:
        recs = ticker_obj.recommendations
        if recs is None or recs.empty:
            return None
        result = []
        for _, row in recs.tail(5).iterrows():
            result.append({
                "firm": _safe_str(row.get("Firm")),
                "action": _safe_str(row.get("Action") or row.get("To Grade")),
                "rating": _safe_str(row.get("To Grade") or row.get("Rating")),
            })
        return result if result else None
    except Exception:
        return None


def get_company_dataset(ticker: str) -> Dict:
    """
    Retrieve a full company dataset for a ticker using yfinance (free, no API key).
    Returns a dict with nine keys. Missing fields are None. Never raises.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        result = _EMPTY_DATASET.copy()

        # Company profile
        employees = None
        try:
            e = info.get("fullTimeEmployees")
            if e is not None:
                employees = int(float(e))
        except (TypeError, ValueError):
            pass
        result["company_profile"] = {
            "name": _safe_str(info.get("longName") or info.get("shortName")),
            "description": _safe_str(info.get("longBusinessSummary")),
            "ceo": None,
            "employees": employees,
            "address": _safe_str(info.get("address1")),
        }

        result["sector"]    = _safe_str(info.get("sector"))
        result["industry"]  = _safe_str(info.get("industry"))
        result["market_cap"]= _safe_float(info.get("marketCap"))
        result["pe_ratio"]  = _safe_float(info.get("trailingPE"))
        result["eps"]       = _safe_float(info.get("trailingEps"))
        result["revenue_growth"] = _safe_float(info.get("revenueGrowth"))

        # Latest price
        price = info.get("regularMarketPrice") or info.get("previousClose")
        result["latest_price"] = _safe_float(price)

        # Analyst recommendations
        result["analyst_recommendations"] = _parse_recommendations(t)

        return result
    except Exception:
        return _EMPTY_DATASET.copy()
