import datetime
import math
import unittest

import numpy as np

from data.risk import calculate_risk_metrics


def _make_returns_data(prices_by_ticker, start_date="2020-01-02"):
    """Build dict of ticker → list[dict] matching get_stock_history() output."""
    result = {}
    for ticker, prices in prices_by_ticker.items():
        records = []
        base = datetime.date.fromisoformat(start_date)
        for i, price in enumerate(prices):
            records.append({
                "date": (base + datetime.timedelta(days=i)).isoformat(),
                "open": float(price),
                "high": float(price),
                "low": float(price),
                "close": float(price),
                "volume": 1000000,
            })
        result[ticker] = records
    return result


_STABLE   = [100.0 + i * 0.1 for i in range(300)]
_FLAT     = [100.0] * 300
_VOLATILE = [100.0 if i % 2 == 0 else 90.0 for i in range(300)]


class TestCalculateRiskMetricsSchema(unittest.TestCase):

    def test_result_has_exactly_six_keys(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertEqual(set(result.keys()), {
            "var_1w_95", "cvar_1w_95", "portfolio_volatility",
            "concentration_risk", "risk_level", "warnings",
        })

    def test_all_fields_are_non_none_on_valid_input(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        for key, value in result.items():
            self.assertIsNotNone(value, f"{key} should not be None on valid input")

    def test_risk_level_is_string(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertIsInstance(result["risk_level"], str)

    def test_warnings_is_list(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertIsInstance(result["warnings"], list)


class TestVaRAndCVaR(unittest.TestCase):

    def test_var_is_non_negative(self):
        data = _make_returns_data({"AAPL": _VOLATILE, "MSFT": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertGreaterEqual(result["var_1w_95"], 0.0)

    def test_cvar_is_at_least_as_large_as_var(self):
        data = _make_returns_data({"AAPL": _VOLATILE, "MSFT": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertGreaterEqual(result["cvar_1w_95"], result["var_1w_95"])

    def test_var_is_positive_for_volatile_prices(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertGreater(result["var_1w_95"], 0.0)

    def test_var_is_zero_for_flat_prices(self):
        data = _make_returns_data({"AAPL": _FLAT})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertEqual(result["var_1w_95"], 0.0)
        self.assertEqual(result["cvar_1w_95"], 0.0)

    def test_var_calculation_matches_expected_formula(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        prices = _VOLATILE
        log_rets = [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
        expected_daily_var = abs(float(np.percentile(log_rets, 5.0)))
        expected_var_1w = expected_daily_var * math.sqrt(5)
        self.assertAlmostEqual(result["var_1w_95"], expected_var_1w, places=10)

    def test_var_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["var_1w_95"]), float)

    def test_cvar_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["cvar_1w_95"]), float)


class TestConcentration(unittest.TestCase):

    def test_single_ticker_concentration_is_one(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertEqual(result["concentration_risk"], 1.0)

    def test_single_ticker_triggers_single_asset_warning(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        combined = " ".join(result["warnings"]).lower()
        self.assertIn("single asset", combined)

    def test_two_equal_tickers_hhi_is_point_five(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertAlmostEqual(result["concentration_risk"], 0.50, places=5)

    def test_heavy_single_weight_triggers_concentration_warning(self):
        # HHI = 0.8² + 0.2² = 0.68 > 0.40
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.8, "MSFT": 0.2}, data)
        self.assertGreater(result["concentration_risk"], 0.40)
        combined = " ".join(result["warnings"]).lower()
        self.assertIn("concentration", combined)

    def test_concentration_is_python_float(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["concentration_risk"]), float)


class TestRiskLevelClassification(unittest.TestCase):

    def test_single_ticker_volatile_returns_critical(self):
        # HHI = 1.0 >= 0.60 → Critical
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertEqual(result["risk_level"], "Critical")

    def test_two_equal_tickers_stable_returns_high(self):
        # HHI = 0.50 >= 0.40, VaR ≈ tiny → High
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.5, "MSFT": 0.5}, data)
        self.assertEqual(result["risk_level"], "High")

    def test_three_equal_tickers_stable_returns_medium(self):
        # HHI = (1/3)² × 3 ≈ 0.333 >= 0.25, VaR ≈ tiny → Medium
        data = _make_returns_data({"A": _STABLE, "B": _STABLE, "C": _STABLE})
        result = calculate_risk_metrics({"A": 1/3, "B": 1/3, "C": 1/3}, data)
        self.assertEqual(result["risk_level"], "Medium")

    def test_five_equal_tickers_stable_returns_low(self):
        # HHI = 0.04 × 5 = 0.20 < 0.25, VaR ≈ tiny < 0.02 → Low
        data = _make_returns_data({
            "A": _STABLE, "B": _STABLE, "C": _STABLE, "D": _STABLE, "E": _STABLE
        })
        result = calculate_risk_metrics(
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}, data
        )
        self.assertEqual(result["risk_level"], "Low")

    def test_high_var_drives_elevated_risk_level(self):
        # Volatile prices → VaR > 0.10 → Critical regardless of concentration
        data = _make_returns_data({
            "A": _VOLATILE, "B": _VOLATILE, "C": _VOLATILE,
            "D": _VOLATILE, "E": _VOLATILE,
        })
        result = calculate_risk_metrics(
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}, data
        )
        self.assertIn(result["risk_level"], ("High", "Critical"))


class TestWarnings(unittest.TestCase):

    def test_no_warnings_for_diversified_stable_portfolio(self):
        data = _make_returns_data({
            "A": _STABLE, "B": _STABLE, "C": _STABLE, "D": _STABLE, "E": _STABLE
        })
        result = calculate_risk_metrics(
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}, data
        )
        self.assertEqual(result["warnings"], [])

    def test_var_warning_fires_for_volatile_prices(self):
        data = _make_returns_data({
            "A": _VOLATILE, "B": _VOLATILE, "C": _VOLATILE,
            "D": _VOLATILE, "E": _VOLATILE,
        })
        result = calculate_risk_metrics(
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}, data
        )
        combined = " ".join(result["warnings"]).lower()
        self.assertIn("var", combined)

    def test_concentration_warning_fires_for_heavy_single_weight(self):
        data = _make_returns_data({"AAPL": _STABLE, "MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 0.8, "MSFT": 0.2}, data)
        combined = " ".join(result["warnings"]).lower()
        self.assertIn("concentration", combined)

    def test_single_asset_warning_fires_for_one_ticker(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        combined = " ".join(result["warnings"]).lower()
        self.assertIn("single asset", combined)

    def test_warnings_list_may_be_empty(self):
        data = _make_returns_data({
            "A": _STABLE, "B": _STABLE, "C": _STABLE, "D": _STABLE, "E": _STABLE
        })
        result = calculate_risk_metrics(
            {"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2}, data
        )
        self.assertIsInstance(result["warnings"], list)
        self.assertEqual(len(result["warnings"]), 0)


class TestEdgeCases(unittest.TestCase):

    def test_none_weights_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics(None, data)
        self.assertIsNone(result["var_1w_95"])
        self.assertIsNone(result["risk_level"])

    def test_empty_weights_dict_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({}, data)
        self.assertIsNone(result["var_1w_95"])

    def test_none_returns_data_returns_empty_result(self):
        result = calculate_risk_metrics({"AAPL": 1.0}, None)
        self.assertIsNone(result["var_1w_95"])

    def test_empty_returns_data_returns_empty_result(self):
        result = calculate_risk_metrics({"AAPL": 1.0}, {})
        self.assertIsNone(result["var_1w_95"])

    def test_fully_mismatched_tickers_returns_empty_result(self):
        data = _make_returns_data({"MSFT": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIsNone(result["var_1w_95"])

    def test_fewer_than_two_aligned_rows_returns_empty_result(self):
        data = {"AAPL": [{"date": "2020-01-02", "close": 100.0,
                          "open": 100.0, "high": 100.0, "low": 100.0, "volume": 1}]}
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIsNone(result["var_1w_95"])

    def test_flat_prices_return_zero_var_without_error(self):
        data = _make_returns_data({"AAPL": _FLAT})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIsNotNone(result["var_1w_95"])
        self.assertEqual(result["var_1w_95"], 0.0)
        self.assertEqual(result["cvar_1w_95"], 0.0)

    def test_confidence_level_zero_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data, confidence_level=0.0)
        self.assertIsNone(result["var_1w_95"])

    def test_confidence_level_one_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data, confidence_level=1.0)
        self.assertIsNone(result["var_1w_95"])

    def test_horizon_days_zero_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data, horizon_days=0)
        self.assertIsNone(result["var_1w_95"])

    def test_horizon_days_negative_returns_empty_result(self):
        data = _make_returns_data({"AAPL": _STABLE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data, horizon_days=-1)
        self.assertIsNone(result["var_1w_95"])

    def test_no_exception_raised_on_invalid_input(self):
        try:
            result = calculate_risk_metrics(None, None)
            self.assertIsNone(result["var_1w_95"])
        except Exception as exc:
            self.fail(f"calculate_risk_metrics raised {exc!r} on invalid input")


class TestTypeSafety(unittest.TestCase):

    def test_var_1w_95_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["var_1w_95"]), float)

    def test_cvar_1w_95_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["cvar_1w_95"]), float)

    def test_portfolio_volatility_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["portfolio_volatility"]), float)

    def test_concentration_risk_is_python_float(self):
        data = _make_returns_data({"AAPL": _VOLATILE})
        result = calculate_risk_metrics({"AAPL": 1.0}, data)
        self.assertIs(type(result["concentration_risk"]), float)


if __name__ == "__main__":
    unittest.main()
