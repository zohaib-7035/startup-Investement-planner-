import datetime
from typing import Union

import yfinance as yf


def get_stock_history(
    symbol: str,
    start_date: Union[str, datetime.date, datetime.datetime],
    end_date: Union[str, datetime.date, datetime.datetime],
) -> list[dict]:
    """
    Fetch daily OHLCV history for a stock symbol between start_date and end_date (inclusive).
    Returns a list of dicts sorted ascending by date. Returns [] for empty ranges,
    future dates, weekend/holiday-only ranges, and unknown tickers.
    """
    start_str = _to_date_str(start_date)
    # yfinance end is exclusive — add one day so end_date is included
    end_str = _to_date_str(
        _parse_date(end_date) + datetime.timedelta(days=1)
    )

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_str, end=end_str, interval="1d", auto_adjust=False)
    except Exception:
        return []

    if df.empty:
        return []

    # Normalise column names to lowercase to guard against yfinance version drift
    df.columns = [c.lower() for c in df.columns]

    # Strip timezone from DatetimeIndex before formatting
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    records = []
    for ts, row in df.iterrows():
        records.append({
            "date": ts.strftime("%Y-%m-%d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        })

    records.sort(key=lambda r: r["date"])
    return records


def _parse_date(value: Union[str, datetime.date, datetime.datetime]) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def _to_date_str(value: Union[str, datetime.date, datetime.datetime]) -> str:
    return _parse_date(value).isoformat()


def _safe_float(value) -> "float | None":
    if value is None or isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_fundamentals(symbol: str) -> dict:
    """
    Fetch the latest fundamental metrics for a stock symbol via yfinance.
    Returns a dict with exactly five keys: pe_ratio, pb_ratio, debt_to_equity,
    eps_last, eps_surprise. Missing or unavailable values are None.
    Never raises — all exceptions are caught and result in all-None output.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        # yfinance returns {} for invalid or delisted tickers — no exception raised
        if not info:
            return {"pe_ratio": None, "pb_ratio": None, "debt_to_equity": None, "eps_last": None, "eps_surprise": None}

        eps_surprise = None
        try:
            eh = ticker.earnings_history
            if eh is not None and not eh.empty and "epsDifference" in eh.columns:
                eps_surprise = _safe_float(eh["epsDifference"].iloc[-1])
        except Exception:
            pass

        return {
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "eps_last": _safe_float(info.get("trailingEps")),
            "eps_surprise": eps_surprise,
        }
    except Exception:
        return {"pe_ratio": None, "pb_ratio": None, "debt_to_equity": None, "eps_last": None, "eps_surprise": None}
