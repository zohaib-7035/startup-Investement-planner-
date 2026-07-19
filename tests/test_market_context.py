"""Tests for data/market_context.py stub surface."""
from data.market_context import get_macro_indicators, get_yield_curve, get_yield_curve_signal


def test_get_macro_indicators_returns_dict():
    result = get_macro_indicators()
    assert isinstance(result, dict)


def test_get_yield_curve_returns_dict():
    result = get_yield_curve()
    assert isinstance(result, dict)


def test_get_yield_curve_signal_returns_dict_with_signal_key():
    result = get_yield_curve_signal()
    assert isinstance(result, dict)
    assert "signal" in result
