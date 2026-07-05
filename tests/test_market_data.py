import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from data.market_data import (
    get_sector_performance,
    get_commodities,
    get_currencies,
    get_market_breadth,
    get_market_snapshot,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_ticker(info_price=None, history_closes=None):
    mock_t = MagicMock()
    mock_t.info = {}
    if info_price is not None:
        mock_t.info = {"regularMarketPrice": info_price}
    if history_closes is not None:
        idx = pd.date_range(end=datetime.date.today(), periods=len(history_closes), freq="D")
        df = pd.DataFrame({"Close": history_closes}, index=idx)
        mock_t.history.return_value = df
    else:
        mock_t.history.return_value = pd.DataFrame()
    return mock_t


def _mock_ticker_factory(info_price=150.0, history_closes=None):
    """Returns a callable that produces a mock Ticker for any symbol."""
    if history_closes is None:
        history_closes = [100.0, 101.0]
    def factory(symbol):
        return _mock_ticker(info_price=info_price, history_closes=history_closes)
    return factory


# ── get_sector_performance ─────────────────────────────────────────────────────

class TestGetSectorPerformance:
    def test_returns_list(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_sector_performance()
        assert isinstance(result, list)

    def test_returns_11_entries(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_sector_performance()
        assert len(result) == 11

    def test_each_entry_has_required_keys(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_sector_performance()
        for entry in result:
            assert {"sector", "symbol", "change_1d_pct"}.issubset(set(entry.keys()))

    def test_change_1d_pct_is_float_or_none(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_sector_performance()
        for entry in result:
            assert isinstance(entry["change_1d_pct"], (float, type(None)))

    def test_yfinance_exception_returns_none_for_change(self):
        with patch("data.market_data.yf.Ticker", side_effect=Exception("network")):
            result = get_sector_performance()
        assert isinstance(result, list)
        for entry in result:
            assert entry["change_1d_pct"] is None

    def test_sorted_descending_by_change(self):
        changes = [0.5, 1.0, -0.5, 0.2, 0.8, -1.0, 0.0, 0.3, 1.5, -0.2, 0.1]
        call_count = {"n": 0}
        def factory(symbol):
            i = call_count["n"] % len(changes)
            call_count["n"] += 1
            return _mock_ticker(
                info_price=None,
                history_closes=[100.0, 100.0 * (1 + changes[i] / 100)],
            )
        with patch("data.market_data.yf.Ticker", side_effect=factory):
            result = get_sector_performance()
        change_vals = [e["change_1d_pct"] for e in result if e["change_1d_pct"] is not None]
        assert change_vals == sorted(change_vals, reverse=True)


# ── get_commodities ────────────────────────────────────────────────────────────

class TestGetCommodities:
    def test_returns_list(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_commodities()
        assert isinstance(result, list)

    def test_returns_7_entries(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_commodities()
        assert len(result) == 7

    def test_each_entry_has_required_keys(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_commodities()
        for entry in result:
            assert {"commodity", "symbol", "price", "change_1d_pct"}.issubset(set(entry.keys()))

    def test_price_is_float_or_none(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory(info_price=1800.0)):
            result = get_commodities()
        for entry in result:
            assert isinstance(entry["price"], (float, type(None)))

    def test_error_returns_none_fields(self):
        with patch("data.market_data.yf.Ticker", side_effect=Exception("timeout")):
            result = get_commodities()
        for entry in result:
            assert entry["price"] is None
            assert entry["change_1d_pct"] is None


# ── get_currencies ─────────────────────────────────────────────────────────────

class TestGetCurrencies:
    def test_returns_list(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_currencies()
        assert isinstance(result, list)

    def test_returns_7_entries(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_currencies()
        assert len(result) == 7

    def test_each_entry_has_required_keys(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_currencies()
        for entry in result:
            assert {"pair", "symbol", "rate", "change_1d_pct"}.issubset(set(entry.keys()))

    def test_eurusd_pair_is_present(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_currencies()
        pairs = {e["pair"] for e in result}
        assert "EUR/USD" in pairs


# ── get_market_breadth ─────────────────────────────────────────────────────────

class TestGetMarketBreadth:
    def test_returns_list(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_breadth()
        assert isinstance(result, list)

    def test_returns_5_entries(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_breadth()
        assert len(result) == 5

    def test_each_entry_has_required_keys(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_breadth()
        for entry in result:
            assert {"index", "symbol", "value", "change_1d_pct"}.issubset(set(entry.keys()))

    def test_vix_entry_present(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_breadth()
        names = {e["index"] for e in result}
        assert "VIX" in names


# ── get_market_snapshot ────────────────────────────────────────────────────────

class TestGetMarketSnapshot:
    def test_returns_dict_with_four_keys(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_snapshot()
        assert set(result.keys()) == {"indices", "sectors", "commodities", "currencies"}

    def test_all_values_are_lists(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_snapshot()
        for key, val in result.items():
            assert isinstance(val, list), f"{key} should be a list"

    def test_indices_count_is_5(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_snapshot()
        assert len(result["indices"]) == 5

    def test_sectors_count_is_11(self):
        with patch("data.market_data.yf.Ticker", side_effect=_mock_ticker_factory()):
            result = get_market_snapshot()
        assert len(result["sectors"]) == 11
