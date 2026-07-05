import json
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd
import numpy as np
import pytest

from data.openbb_client import get_company_dataset

EXPECTED_KEYS = {
    "company_profile",
    "latest_price",
    "market_cap",
    "pe_ratio",
    "eps",
    "revenue_growth",
    "sector",
    "industry",
    "analyst_recommendations",
}


def _make_info(
    long_name="Apple Inc.",
    description="Designs and sells electronics.",
    full_time_employees=164000,
    address1="One Apple Park Way",
    sector="Technology",
    industry="Consumer Electronics",
    market_cap=2_950_000_000_000.0,
    trailing_pe=28.5,
    trailing_eps=6.43,
    revenue_growth=0.051,
    regular_market_price=189.30,
):
    return {
        "longName": long_name,
        "longBusinessSummary": description,
        "fullTimeEmployees": full_time_employees,
        "address1": address1,
        "sector": sector,
        "industry": industry,
        "marketCap": market_cap,
        "trailingPE": trailing_pe,
        "trailingEps": trailing_eps,
        "revenueGrowth": revenue_growth,
        "regularMarketPrice": regular_market_price,
    }


def _make_recs_df(firms=None, actions=None, grades=None):
    if firms is None:
        firms = ["Goldman Sachs"]
    if actions is None:
        actions = ["Upgrades"]
    if grades is None:
        grades = ["Buy"]
    return pd.DataFrame({
        "Firm": firms,
        "Action": actions,
        "To Grade": grades,
    })


def _make_ticker(info=None, recs=None, recs_raises=False, info_raises=False):
    mock_t = MagicMock()
    if info_raises:
        type(mock_t).info = PropertyMock(side_effect=Exception("network error"))
    else:
        mock_t.info = info if info is not None else {}
    if recs_raises:
        type(mock_t).recommendations = PropertyMock(
            side_effect=Exception("recs unavailable")
        )
    else:
        mock_t.recommendations = recs
    return mock_t


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_result_has_exactly_nine_keys():
    ticker = _make_ticker(info=_make_info(), recs=_make_recs_df())
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert len(result) == 9
    assert set(result.keys()) == EXPECTED_KEYS


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_all_fields_populated_with_correct_types():
    ticker = _make_ticker(info=_make_info(), recs=_make_recs_df())
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert isinstance(result["company_profile"], dict)
    assert type(result["latest_price"]) is float
    assert type(result["market_cap"]) is float
    assert type(result["pe_ratio"]) is float
    assert type(result["eps"]) is float
    assert type(result["revenue_growth"]) is float
    assert isinstance(result["sector"], str)
    assert isinstance(result["industry"], str)
    assert isinstance(result["analyst_recommendations"], list)


def test_happy_path_field_values_are_correct():
    ticker = _make_ticker(
        info=_make_info(
            long_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=2_950_000_000_000.0,
            trailing_pe=28.5,
            trailing_eps=6.43,
            revenue_growth=0.051,
            regular_market_price=189.30,
        ),
        recs=_make_recs_df(firms=["Goldman Sachs"], actions=["Upgrades"], grades=["Buy"]),
    )
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert result["sector"] == "Technology"
    assert result["industry"] == "Consumer Electronics"
    assert result["latest_price"] == pytest.approx(189.30)
    assert result["market_cap"] == pytest.approx(2_950_000_000_000.0)
    assert result["pe_ratio"] == pytest.approx(28.5)
    assert result["eps"] == pytest.approx(6.43)
    assert result["revenue_growth"] == pytest.approx(0.051)
    assert result["company_profile"]["name"] == "Apple Inc."
    recs = result["analyst_recommendations"]
    assert len(recs) == 1
    assert recs[0]["firm"] == "Goldman Sachs"


def test_company_profile_has_expected_keys():
    ticker = _make_ticker(info=_make_info(), recs=None)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    profile = result["company_profile"]
    assert isinstance(profile, dict)
    assert "name" in profile
    assert "description" in profile
    assert "employees" in profile


# ---------------------------------------------------------------------------
# Numpy scalar normalisation
# ---------------------------------------------------------------------------

def test_numpy_scalar_numeric_fields_are_converted_to_python_float():
    info = _make_info(
        market_cap=np.float64(2_950_000_000_000.0),
        trailing_pe=np.float64(28.5),
        trailing_eps=np.float64(6.43),
        revenue_growth=np.float64(0.051),
        regular_market_price=np.float64(189.30),
    )
    ticker = _make_ticker(info=info, recs=None)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert type(result["latest_price"]) is float
    assert type(result["market_cap"]) is float
    assert type(result["pe_ratio"]) is float
    assert type(result["eps"]) is float
    assert type(result["revenue_growth"]) is float


# ---------------------------------------------------------------------------
# Partial failures — one part fails, others succeed
# ---------------------------------------------------------------------------

def test_recommendations_raises_leaves_other_fields_populated():
    ticker = _make_ticker(info=_make_info(), recs_raises=True)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert result["analyst_recommendations"] is None
    assert result["latest_price"] == pytest.approx(189.30)
    assert isinstance(result["company_profile"], dict)
    assert result["sector"] == "Technology"


def test_empty_recs_dataframe_returns_none():
    ticker = _make_ticker(info=_make_info(), recs=pd.DataFrame())
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert result["analyst_recommendations"] is None


def test_none_recommendations_returns_none():
    ticker = _make_ticker(info=_make_info(), recs=None)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert result["analyst_recommendations"] is None


# ---------------------------------------------------------------------------
# Empty / invalid info — fields become None without raising
# ---------------------------------------------------------------------------

def test_empty_info_dict_returns_none_numeric_fields():
    ticker = _make_ticker(info={}, recs=None)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("INVALID_XYZ")
    assert set(result.keys()) == EXPECTED_KEYS
    assert result["latest_price"] is None
    assert result["market_cap"] is None
    assert result["pe_ratio"] is None
    assert result["eps"] is None
    assert result["revenue_growth"] is None
    assert result["sector"] is None
    assert result["industry"] is None


def test_missing_pe_and_eps_returns_none_for_those_fields():
    info = _make_info()
    del info["trailingPE"]
    del info["trailingEps"]
    ticker = _make_ticker(info=info, recs=None)
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    assert result["pe_ratio"] is None
    assert result["eps"] is None
    assert result["latest_price"] == pytest.approx(189.30)


# ---------------------------------------------------------------------------
# Network / SDK exception — all-None fallback, no exception raised
# ---------------------------------------------------------------------------

def test_ticker_exception_returns_all_none_dict():
    with patch("data.openbb_client.yf.Ticker", side_effect=Exception("network error")):
        result = get_company_dataset("AAPL")
    assert set(result.keys()) == EXPECTED_KEYS
    assert all(v is None for v in result.values())


def test_never_raises_on_bad_ticker():
    with patch("data.openbb_client.yf.Ticker", side_effect=RuntimeError("crash")):
        try:
            result = get_company_dataset("BAD")
            assert set(result.keys()) == EXPECTED_KEYS
        except Exception as exc:
            pytest.fail(f"get_company_dataset raised: {exc}")


# ---------------------------------------------------------------------------
# JSON serialisability
# ---------------------------------------------------------------------------

def test_result_is_json_serialisable_happy_path():
    ticker = _make_ticker(
        info=_make_info(),
        recs=_make_recs_df(),
    )
    with patch("data.openbb_client.yf.Ticker", return_value=ticker):
        result = get_company_dataset("AAPL")
    serialised = json.dumps(result)
    assert isinstance(serialised, str)


def test_result_is_json_serialisable_all_none_fallback():
    with patch("data.openbb_client.yf.Ticker", side_effect=Exception("crash")):
        result = get_company_dataset("AAPL")
    serialised = json.dumps(result)
    assert isinstance(serialised, str)
