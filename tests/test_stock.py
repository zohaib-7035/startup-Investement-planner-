import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from data.stock import get_fundamentals, get_stock_history

EXPECTED_KEYS = {"date", "open", "high", "low", "close", "volume"}


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a yfinance-style DataFrame from a list of row dicts."""
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    index = pd.DatetimeIndex(
        [pd.Timestamp(r["date"], tz="America/New_York") for r in rows]
    )
    data = {
        "Open": [r["open"] for r in rows],
        "High": [r["high"] for r in rows],
        "Low": [r["low"] for r in rows],
        "Close": [r["close"] for r in rows],
        "Volume": [r["volume"] for r in rows],
    }
    return pd.DataFrame(data, index=index)


def _mock_ticker(df: pd.DataFrame):
    """Return a patched yfinance.Ticker whose history() returns df."""
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.history.return_value = df
    return mock_ticker_instance


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_returns_correct_schema():
    rows = [
        {"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 1000000},
        {"date": "2024-01-03", "open": 186.0, "high": 188.0, "low": 185.0, "close": 187.0, "volume": 1100000},
    ]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-03")

    assert len(result) == 2
    for record in result:
        assert set(record.keys()) == EXPECTED_KEYS


def test_happy_path_returns_only_six_keys():
    rows = [{"date": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 500000}]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-02")

    assert len(result) == 1
    assert set(result[0].keys()) == EXPECTED_KEYS


def test_dates_are_sorted_ascending():
    rows = [
        {"date": "2024-01-04", "open": 188.0, "high": 190.0, "low": 187.0, "close": 189.0, "volume": 900000},
        {"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 1000000},
        {"date": "2024-01-03", "open": 186.0, "high": 188.0, "low": 185.0, "close": 187.0, "volume": 1100000},
    ]
    # deliberately out of order to exercise the sort guard
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-04")

    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_numeric_types_are_python_native():
    rows = [{"date": "2024-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 500000}]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-02")

    r = result[0]
    assert type(r["open"]) is float
    assert type(r["high"]) is float
    assert type(r["low"]) is float
    assert type(r["close"]) is float
    assert type(r["volume"]) is int


# ---------------------------------------------------------------------------
# Single-day range on a trading day
# ---------------------------------------------------------------------------

def test_single_trading_day_returns_one_record():
    rows = [{"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 1000000}]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-02")

    assert len(result) == 1
    assert result[0]["date"] == "2024-01-02"


# ---------------------------------------------------------------------------
# Single-day range on a weekend / holiday → empty list
# ---------------------------------------------------------------------------

def test_weekend_day_returns_empty_list():
    empty_df = _make_df([])

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(empty_df)):
        result = get_stock_history("AAPL", "2024-01-06", "2024-01-06")  # Saturday

    assert result == []


# ---------------------------------------------------------------------------
# Future date range → empty list
# ---------------------------------------------------------------------------

def test_future_date_range_returns_empty_list():
    empty_df = _make_df([])

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(empty_df)):
        result = get_stock_history("AAPL", "2099-01-01", "2099-01-31")

    assert result == []


# ---------------------------------------------------------------------------
# Invalid ticker → empty list (no raw exception)
# ---------------------------------------------------------------------------

def test_invalid_ticker_returns_empty_list():
    empty_df = _make_df([])

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(empty_df)):
        result = get_stock_history("INVALID_TICKER_XYZ", "2024-01-02", "2024-01-05")

    assert result == []


def test_yfinance_exception_returns_empty_list():
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.history.side_effect = Exception("network error")

    with patch("data.stock.yf.Ticker", return_value=mock_ticker_instance):
        result = get_stock_history("AAPL", "2024-01-02", "2024-01-05")

    assert result == []


# ---------------------------------------------------------------------------
# date input types: accepts str, datetime.date, datetime.datetime
# ---------------------------------------------------------------------------

def test_accepts_date_objects_as_input():
    rows = [{"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 1000000}]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history(
            "AAPL",
            datetime.date(2024, 1, 2),
            datetime.date(2024, 1, 2),
        )

    assert len(result) == 1
    assert result[0]["date"] == "2024-01-02"


def test_accepts_datetime_objects_as_input():
    rows = [{"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 1000000}]
    df = _make_df(rows)

    with patch("data.stock.yf.Ticker", return_value=_mock_ticker(df)):
        result = get_stock_history(
            "AAPL",
            datetime.datetime(2024, 1, 2, 9, 30),
            datetime.datetime(2024, 1, 2, 16, 0),
        )

    assert len(result) == 1
    assert result[0]["date"] == "2024-01-02"


# ===========================================================================
# get_fundamentals tests
# ===========================================================================

EXPECTED_FUNDAMENTALS_KEYS = {"pe_ratio", "pb_ratio", "debt_to_equity", "eps_last", "eps_surprise"}


def _make_earnings_history(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["epsDifference"])
    return pd.DataFrame(rows)


def _mock_fundamentals_ticker(info: dict, earnings_history: "pd.DataFrame | None" = None):
    mock = MagicMock()
    mock.info = info
    mock.earnings_history = earnings_history if earnings_history is not None else pd.DataFrame(columns=["epsDifference"])
    return mock


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_fundamentals_returns_correct_schema():
    info = {"trailingPE": 27.5, "priceToBook": 7.2, "debtToEquity": 0.3, "trailingEps": 5.4}
    eh = _make_earnings_history([{"epsDifference": 0.12}])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert set(result.keys()) == EXPECTED_FUNDAMENTALS_KEYS


def test_fundamentals_eps_surprise_uses_most_recent_earnings_row():
    info = {"trailingPE": 27.5, "priceToBook": 7.2, "debtToEquity": 0.3, "trailingEps": 5.4}
    # older row first, newer row last — .iloc[-1] must pick 0.20, not 0.05
    eh = _make_earnings_history([{"epsDifference": 0.05}, {"epsDifference": 0.20}])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert result["eps_surprise"] == 0.20


def test_fundamentals_all_numeric_values_are_python_float():
    info = {"trailingPE": 27.5, "priceToBook": 7.2, "debtToEquity": 0.3, "trailingEps": 5.4}
    eh = _make_earnings_history([{"epsDifference": 0.12}])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert type(result["pe_ratio"]) is float
    assert type(result["pb_ratio"]) is float
    assert type(result["debt_to_equity"]) is float
    assert type(result["eps_last"]) is float
    assert type(result["eps_surprise"]) is float


def test_fundamentals_numpy_scalar_values_are_converted_to_python_float():
    info = {
        "trailingPE": np.float64(27.5),
        "priceToBook": np.float64(7.2),
        "debtToEquity": np.float64(0.3),
        "trailingEps": np.float64(5.4),
    }
    eh = _make_earnings_history([{"epsDifference": np.float64(0.12)}])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert type(result["pe_ratio"]) is float
    assert type(result["eps_surprise"]) is float


def test_fundamentals_values_are_correct():
    info = {"trailingPE": 27.5, "priceToBook": 7.2, "debtToEquity": 0.3, "trailingEps": 5.4}
    eh = _make_earnings_history([{"epsDifference": 0.12}])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert result["pe_ratio"] == 27.5
    assert result["pb_ratio"] == 7.2
    assert result["debt_to_equity"] == 0.3
    assert result["eps_last"] == 5.4
    assert result["eps_surprise"] == 0.12


# ---------------------------------------------------------------------------
# Partial data — eps_surprise missing
# ---------------------------------------------------------------------------

def test_fundamentals_eps_surprise_is_none_when_earnings_history_empty():
    info = {"trailingPE": 27.5, "priceToBook": 7.2, "debtToEquity": 0.3, "trailingEps": 5.4}
    eh = _make_earnings_history([])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert result["eps_surprise"] is None
    assert type(result["pe_ratio"]) is float


def test_fundamentals_na_string_values_are_returned_as_none():
    info = {"trailingPE": "N/A", "priceToBook": 7.2, "debtToEquity": None, "trailingEps": "N/A"}
    eh = _make_earnings_history([])

    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker(info, eh)):
        result = get_fundamentals("AAPL")

    assert result["pe_ratio"] is None
    assert result["eps_last"] is None
    assert result["debt_to_equity"] is None
    assert type(result["pb_ratio"]) is float


# ---------------------------------------------------------------------------
# Invalid ticker — empty info dict
# ---------------------------------------------------------------------------

def test_fundamentals_invalid_ticker_returns_all_none():
    with patch("data.stock.yf.Ticker", return_value=_mock_fundamentals_ticker({})):
        result = get_fundamentals("INVALID_TICKER_XYZ")

    assert set(result.keys()) == EXPECTED_FUNDAMENTALS_KEYS
    assert all(v is None for v in result.values())


# ---------------------------------------------------------------------------
# yfinance exception
# ---------------------------------------------------------------------------

def test_fundamentals_yfinance_exception_returns_all_none():
    with patch("data.stock.yf.Ticker", side_effect=Exception("network error")):
        result = get_fundamentals("AAPL")

    assert set(result.keys()) == EXPECTED_FUNDAMENTALS_KEYS
    assert all(v is None for v in result.values())
