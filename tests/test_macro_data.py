from unittest.mock import MagicMock, patch
import datetime

import pandas as pd
import pytest

from data.macro_data import (
    _fetch_yf_latest,
    _fetch_fred_latest,
    _fetch_fred_series,
    get_macro_indicators,
    get_yield_curve_signal,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_df(closes, start="2025-06-01"):
    idx = pd.date_range(start=start, periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes}, index=idx)


def _mock_ticker(closes=None):
    m = MagicMock()
    m.history.return_value = _mock_df(closes or [4.5, 4.372])
    return m


def _fred_response(value="5.33", date="2025-01-01"):
    m = MagicMock()
    m.json.return_value = {"observations": [{"date": date, "value": value}]}
    m.raise_for_status = MagicMock()
    return m


def _fred_error_response():
    from requests import HTTPError
    m = MagicMock()
    m.raise_for_status.side_effect = HTTPError("503")
    return m


# ── _fetch_yf_latest ───────────────────────────────────────────────────────────

class TestFetchYfLatest:
    def test_returns_dict_with_value_and_date(self):
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker([4.0, 4.372])):
            r = _fetch_yf_latest("^TNX")
        assert r is not None
        assert "value" in r and "date" in r

    def test_value_is_float(self):
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker([4.0, 4.372])):
            r = _fetch_yf_latest("^TNX")
        assert isinstance(r["value"], float)
        assert r["value"] == pytest.approx(4.372)

    def test_date_is_string(self):
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker([4.372])):
            r = _fetch_yf_latest("^TNX")
        assert isinstance(r["date"], str)
        assert len(r["date"]) == 10  # YYYY-MM-DD

    def test_empty_df_returns_none(self):
        t = MagicMock()
        t.history.return_value = pd.DataFrame()
        with patch("data.macro_data.yf.Ticker", return_value=t):
            r = _fetch_yf_latest("^TNX")
        assert r is None

    def test_exception_returns_none(self):
        with patch("data.macro_data.yf.Ticker", side_effect=Exception("network")):
            r = _fetch_yf_latest("^TNX")
        assert r is None


# ── _fetch_fred_latest ─────────────────────────────────────────────────────────

class TestFetchFredLatest:
    def test_returns_value_and_date_on_success(self):
        with patch("data.macro_data.requests.get", return_value=_fred_response("5.33", "2025-01-01")):
            r = _fetch_fred_latest("FEDFUNDS", "testkey")
        assert r is not None
        assert r["value"] == pytest.approx(5.33)
        assert r["date"] == "2025-01-01"

    def test_dot_value_returns_none(self):
        with patch("data.macro_data.requests.get", return_value=_fred_response(".", "2025-01-01")):
            r = _fetch_fred_latest("FEDFUNDS", "testkey")
        assert r is None

    def test_http_error_returns_none(self):
        with patch("data.macro_data.requests.get", return_value=_fred_error_response()):
            r = _fetch_fred_latest("FEDFUNDS", "testkey")
        assert r is None

    def test_network_error_returns_none(self):
        with patch("data.macro_data.requests.get", side_effect=Exception("timeout")):
            r = _fetch_fred_latest("FEDFUNDS", "testkey")
        assert r is None

    def test_empty_observations_returns_none(self):
        m = MagicMock()
        m.json.return_value = {"observations": []}
        m.raise_for_status = MagicMock()
        with patch("data.macro_data.requests.get", return_value=m):
            r = _fetch_fred_latest("FEDFUNDS", "testkey")
        assert r is None


# ── _fetch_fred_series ─────────────────────────────────────────────────────────

class TestFetchFredSeries:
    def test_returns_none_without_api_key(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.requests.get") as mock_get:
            result = _fetch_fred_series("FEDFUNDS", limit=1)
        mock_get.assert_not_called()
        assert result is None

    def test_returns_list_with_api_key(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")
        resp = MagicMock()
        resp.json.return_value = {"observations": [{"date": "2025-01-01", "value": "5.33"}]}
        resp.raise_for_status = MagicMock()
        with patch("data.macro_data.requests.get", return_value=resp):
            result = _fetch_fred_series("FEDFUNDS", limit=1)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_each_entry_has_date_and_value(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")
        resp = MagicMock()
        resp.json.return_value = {"observations": [{"date": "2025-06-01", "value": "5.5"}]}
        resp.raise_for_status = MagicMock()
        with patch("data.macro_data.requests.get", return_value=resp):
            result = _fetch_fred_series("FEDFUNDS")
        assert "date" in result[0] and "value" in result[0]

    def test_dot_value_becomes_none(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")
        resp = MagicMock()
        resp.json.return_value = {"observations": [{"date": "2025-06-01", "value": "."}]}
        resp.raise_for_status = MagicMock()
        with patch("data.macro_data.requests.get", return_value=resp):
            result = _fetch_fred_series("FEDFUNDS")
        assert result[0]["value"] is None

    def test_network_error_returns_none(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")
        with patch("data.macro_data.requests.get", side_effect=Exception("down")):
            result = _fetch_fred_series("FEDFUNDS")
        assert result is None


# ── get_macro_indicators ───────────────────────────────────────────────────────

class TestGetMacroIndicators:
    def _mock_yf(self, val=4.372):
        t = _mock_ticker([val])
        return t

    def test_returns_dict(self):
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        assert isinstance(r, dict)

    def test_has_fred_key_flag_present(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        assert "_has_fred_key" in r

    def test_fred_key_false_when_not_set(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        assert r["_has_fred_key"] is False

    def test_treasury_keys_present(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        for key in ("10y_treasury", "30y_treasury", "5y_treasury", "13w_tbill"):
            assert key in r, f"missing key: {key}"

    def test_economic_keys_present(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        for key in ("fed_funds_rate", "cpi_yoy", "unemployment_rate", "gdp_growth", "2y_treasury"):
            assert key in r, f"missing key: {key}"

    def test_economic_values_none_without_fred_key(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        for key in ("fed_funds_rate", "cpi_yoy", "unemployment_rate", "gdp_growth", "2y_treasury"):
            assert r[key]["value"] is None

    def test_treasury_values_populated_from_yfinance(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker([4.372])):
            r = get_macro_indicators()
        # At least one treasury should have a non-None value
        treasury_vals = [r[k]["value"] for k in ("10y_treasury", "30y_treasury", "5y_treasury", "13w_tbill")]
        assert any(v is not None for v in treasury_vals)

    def test_each_indicator_has_four_subkeys(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        for key, item in r.items():
            if key == "_has_fred_key":
                continue
            assert {"value", "date", "description", "series_id"}.issubset(set(item.keys())), \
                f"{key} missing required subkeys"

    def test_description_is_nonempty_string(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with patch("data.macro_data.yf.Ticker", return_value=_mock_ticker()):
            r = get_macro_indicators()
        for key, item in r.items():
            if key == "_has_fred_key":
                continue
            assert isinstance(item["description"], str) and len(item["description"]) > 0


# ── get_yield_curve_signal ─────────────────────────────────────────────────────

class TestGetYieldCurveSignal:
    def _patch_yf(self, tnx=4.372, irx=3.663):
        def factory(symbol):
            val = tnx if symbol == "^TNX" else irx
            return _mock_ticker([val])
        return factory

    def test_schema_has_three_keys(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf()):
            r = get_yield_curve_signal()
        assert set(r.keys()) == {"signal", "spread", "date"}

    def test_large_spread_returns_normal(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=5.0, irx=3.0)):
            r = get_yield_curve_signal()
        assert r["signal"] == "NORMAL"

    def test_negative_spread_returns_inverted(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=3.5, irx=4.0)):
            r = get_yield_curve_signal()
        assert r["signal"] == "INVERTED"

    def test_small_positive_spread_returns_flat(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=4.0, irx=3.8)):
            r = get_yield_curve_signal()
        assert r["signal"] == "FLAT"

    def test_spread_at_zero_returns_flat(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=4.0, irx=4.0)):
            r = get_yield_curve_signal()
        assert r["signal"] == "FLAT"

    def test_spread_exactly_0_5_returns_normal(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=4.5, irx=4.0)):
            r = get_yield_curve_signal()
        assert r["signal"] == "NORMAL"

    def test_yfinance_error_returns_unknown(self):
        with patch("data.macro_data.yf.Ticker", side_effect=Exception("down")):
            r = get_yield_curve_signal()
        assert r["signal"] == "UNKNOWN"
        assert r["spread"] is None
        assert r["date"] is None

    def test_spread_is_rounded_float(self):
        with patch("data.macro_data.yf.Ticker", side_effect=self._patch_yf(tnx=4.372, irx=3.663)):
            r = get_yield_curve_signal()
        assert isinstance(r["spread"], float)
        assert r["spread"] == pytest.approx(0.709, abs=1e-2)

    def test_empty_df_returns_unknown(self):
        t = MagicMock()
        t.history.return_value = pd.DataFrame()
        with patch("data.macro_data.yf.Ticker", return_value=t):
            r = get_yield_curve_signal()
        assert r["signal"] == "UNKNOWN"
