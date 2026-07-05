"""
Free market data connectors using yfinance only.
Covers: sector performance, commodities, currencies, market breadth, major indices.
No API key required. All data from Yahoo Finance.
"""
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import yfinance as yf

# ── Sector ETFs (SPDR) ────────────────────────────────────────────────────────
_SECTOR_ETFS = {
    "Technology":       "XLK",
    "Healthcare":       "XLV",
    "Financials":       "XLF",
    "Consumer Discr.":  "XLY",
    "Consumer Staples": "XLP",
    "Energy":           "XLE",
    "Industrials":      "XLI",
    "Materials":        "XLB",
    "Real Estate":      "XLRE",
    "Utilities":        "XLU",
    "Communication":    "XLC",
}

# ── Commodity symbols on Yahoo Finance ───────────────────────────────────────
_COMMODITIES = {
    "Gold":       "GC=F",
    "Silver":     "SI=F",
    "Crude Oil":  "CL=F",
    "Natural Gas":"NG=F",
    "Copper":     "HG=F",
    "Wheat":      "ZW=F",
    "Corn":       "ZC=F",
}

# ── Currency pairs on Yahoo Finance ─────────────────────────────────────────
_CURRENCIES = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "USD/CNY": "CNY=X",
    "USD/CHF": "CHF=X",
    "USD/CAD": "CAD=X",
    "AUD/USD": "AUDUSD=X",
}

# ── Market breadth proxies ────────────────────────────────────────────────────
_BREADTH_SYMBOLS = {
    "S&P 500":     "^GSPC",
    "NASDAQ":      "^IXIC",
    "Dow Jones":   "^DJI",
    "Russell 2000":"^RUT",
    "VIX":         "^VIX",
}

_MAX_WORKERS = 12


def _safe_float(val) -> Optional[float]:
    try:
        return round(float(val), 4)
    except (TypeError, ValueError):
        return None


def _fetch_symbol(symbol: str):
    """
    Single yfinance call per symbol: returns (latest_price, pct_change_1d).
    Uses history over the last 7 days to guarantee at least 2 trading sessions.
    """
    try:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=7)
        t = yf.Ticker(symbol)
        df = t.history(start=start.isoformat(), end=end.isoformat(), interval="1d")
        if df is None or df.empty:
            return None, None
        closes = df["Close"].dropna().tolist()
        if not closes:
            return None, None
        price = _safe_float(closes[-1])
        change = None
        if len(closes) >= 2 and closes[-2]:
            change = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
        return price, change
    except Exception:
        return None, None


def _fetch_all(symbols: List[str]) -> Dict[str, tuple]:
    """Fetch all symbols concurrently. Returns {symbol: (price, change)}."""
    results = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        future_to_sym = {ex.submit(_fetch_symbol, sym): sym for sym in symbols}
        for future in as_completed(future_to_sym):
            sym = future_to_sym[future]
            try:
                results[sym] = future.result()
            except Exception:
                results[sym] = (None, None)
    return results


def get_sector_performance() -> List[Dict]:
    """
    Return 1-day % change for each S&P 500 sector via SPDR ETFs.
    Free data source: Yahoo Finance. No API key needed.
    """
    data = _fetch_all(list(_SECTOR_ETFS.values()))
    results = []
    for name, sym in _SECTOR_ETFS.items():
        price, chg = data.get(sym, (None, None))
        results.append({"sector": name, "symbol": sym, "change_1d_pct": chg})
    results.sort(key=lambda x: x["change_1d_pct"] or 0, reverse=True)
    return results


def get_commodities() -> List[Dict]:
    """
    Return latest prices and 1-day change for major commodities.
    Free data source: Yahoo Finance futures symbols. No API key needed.
    """
    data = _fetch_all(list(_COMMODITIES.values()))
    results = []
    for name, sym in _COMMODITIES.items():
        price, chg = data.get(sym, (None, None))
        results.append({"commodity": name, "symbol": sym, "price": price, "change_1d_pct": chg})
    return results


def get_currencies() -> List[Dict]:
    """
    Return latest exchange rates for major currency pairs.
    Free data source: Yahoo Finance forex symbols. No API key needed.
    """
    data = _fetch_all(list(_CURRENCIES.values()))
    results = []
    for name, sym in _CURRENCIES.items():
        price, chg = data.get(sym, (None, None))
        results.append({"pair": name, "symbol": sym, "rate": price, "change_1d_pct": chg})
    return results


def get_market_breadth() -> List[Dict]:
    """
    Return latest values and 1-day change for major indices and VIX.
    Free data source: Yahoo Finance index symbols. No API key needed.
    """
    data = _fetch_all(list(_BREADTH_SYMBOLS.values()))
    results = []
    for name, sym in _BREADTH_SYMBOLS.items():
        price, chg = data.get(sym, (None, None))
        results.append({"index": name, "symbol": sym, "value": price, "change_1d_pct": chg})
    return results


def get_market_snapshot() -> Dict:
    """
    Return a combined snapshot: indices, sectors, commodities, currencies.
    All symbols fetched concurrently for speed. All free via Yahoo Finance.
    """
    all_syms = (
        list(_BREADTH_SYMBOLS.values())
        + list(_SECTOR_ETFS.values())
        + list(_COMMODITIES.values())
        + list(_CURRENCIES.values())
    )
    data = _fetch_all(all_syms)

    indices = []
    for name, sym in _BREADTH_SYMBOLS.items():
        price, chg = data.get(sym, (None, None))
        indices.append({"index": name, "symbol": sym, "value": price, "change_1d_pct": chg})

    sectors = []
    for name, sym in _SECTOR_ETFS.items():
        _, chg = data.get(sym, (None, None))
        sectors.append({"sector": name, "symbol": sym, "change_1d_pct": chg})
    sectors.sort(key=lambda x: x["change_1d_pct"] or 0, reverse=True)

    commodities = []
    for name, sym in _COMMODITIES.items():
        price, chg = data.get(sym, (None, None))
        commodities.append({"commodity": name, "symbol": sym, "price": price, "change_1d_pct": chg})

    currencies = []
    for name, sym in _CURRENCIES.items():
        price, chg = data.get(sym, (None, None))
        currencies.append({"pair": name, "symbol": sym, "rate": price, "change_1d_pct": chg})

    return {
        "indices":     indices,
        "sectors":     sectors,
        "commodities": commodities,
        "currencies":  currencies,
    }
