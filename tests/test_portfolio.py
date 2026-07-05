import unittest
from unittest.mock import patch

from data.portfolio import optimize_portfolio


def _make_history(prices, start_date="2020-01-02"):
    """Build list-of-dicts matching get_stock_history output from a list of close prices."""
    import datetime
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
    return records


_AAPL_PRICES = [150.0 + i * 0.5 for i in range(300)]
_MSFT_PRICES = [280.0 + i * 0.3 for i in range(300)]
_NVDA_PRICES = [400.0 + i * 1.0 for i in range(300)]
_GOOGL_PRICES = [100.0 + i * 0.2 for i in range(300)]

_FOUR_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL"]
_FOUR_HISTORIES = [
    _make_history(_AAPL_PRICES),
    _make_history(_MSFT_PRICES),
    _make_history(_NVDA_PRICES),
    _make_history(_GOOGL_PRICES),
]


class TestOptimizePortfolioSchema(unittest.TestCase):

    @patch("data.portfolio.get_stock_history")
    def test_result_has_correct_four_keys(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        self.assertEqual(set(result.keys()), {"weights", "expected_return", "volatility", "sharpe_ratio"})

    @patch("data.portfolio.get_stock_history")
    def test_weights_sum_to_one(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        self.assertIsNotNone(result["weights"])
        total = sum(result["weights"].values())
        self.assertAlmostEqual(total, 1.0, places=5)

    @patch("data.portfolio.get_stock_history")
    def test_all_weights_non_negative(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        for ticker, w in result["weights"].items():
            self.assertGreaterEqual(w, 0.0, f"weight for {ticker} is negative")

    @patch("data.portfolio.get_stock_history")
    def test_numeric_outputs_are_python_float(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        self.assertIs(type(result["expected_return"]), float)
        self.assertIs(type(result["volatility"]), float)
        self.assertIs(type(result["sharpe_ratio"]), float)

    @patch("data.portfolio.get_stock_history")
    def test_weights_values_are_python_float(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        for ticker, w in result["weights"].items():
            self.assertIs(type(w), float, f"weight for {ticker} is not Python float")

    @patch("data.portfolio.get_stock_history")
    def test_weights_dict_keyed_by_ticker_symbol(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result = optimize_portfolio(_FOUR_TICKERS, 0.5, 5)
        self.assertEqual(set(result["weights"].keys()), set(_FOUR_TICKERS))


class TestOptimizePortfolioDiversification(unittest.TestCase):

    @patch("data.portfolio.get_stock_history")
    def test_risk_tolerance_zero_returns_valid_result(self, mock_gsh):
        low_prices = [100.0 + i * 0.01 for i in range(300)]
        high_prices = [100.0 + i * 1.0 for i in range(300)]
        mock_gsh.side_effect = [
            _make_history(high_prices),
            _make_history(low_prices),
        ] * 10
        result = optimize_portfolio(["AAPL", "MSFT"], 0.0, 1)
        self.assertIsNotNone(result["weights"])
        self.assertAlmostEqual(sum(result["weights"].values()), 1.0, places=5)

    @patch("data.portfolio.get_stock_history")
    def test_risk_tolerance_one_produces_roughly_equal_weights_for_identical_assets(self, mock_gsh):
        flat_prices = [100.0 + i * 0.1 for i in range(300)]
        mock_gsh.side_effect = [
            _make_history(flat_prices),
            _make_history(flat_prices),
            _make_history(flat_prices),
        ] * 10
        result = optimize_portfolio(["AAPL", "MSFT", "NVDA"], 1.0, 1)
        self.assertIsNotNone(result["weights"])
        for w in result["weights"].values():
            self.assertAlmostEqual(w, 1.0 / 3, delta=0.05)


class TestOptimizePortfolioEdgeCases(unittest.TestCase):

    def test_empty_tickers_returns_empty_portfolio(self):
        result = optimize_portfolio([], 0.5, 5)
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    @patch("data.portfolio.get_stock_history")
    def test_single_ticker_returns_weight_of_one(self, mock_gsh):
        mock_gsh.return_value = _make_history(_AAPL_PRICES)
        result = optimize_portfolio(["AAPL"], 0.5, 1)
        self.assertIsNotNone(result["weights"])
        self.assertEqual(set(result["weights"].keys()), {"AAPL"})
        self.assertAlmostEqual(result["weights"]["AAPL"], 1.0, places=5)

    @patch("data.portfolio.get_stock_history")
    def test_single_ticker_stats_are_python_float(self, mock_gsh):
        mock_gsh.return_value = _make_history(_AAPL_PRICES)
        result = optimize_portfolio(["AAPL"], 0.5, 1)
        self.assertIs(type(result["expected_return"]), float)
        self.assertIs(type(result["volatility"]), float)
        self.assertIs(type(result["sharpe_ratio"]), float)

    @patch("data.portfolio.get_stock_history")
    def test_one_failed_ticker_is_dropped_silently(self, mock_gsh):
        mock_gsh.side_effect = [
            [],
            _make_history(_MSFT_PRICES),
            _make_history(_NVDA_PRICES),
        ] * 10
        result = optimize_portfolio(["AAPL", "MSFT", "NVDA"], 0.5, 1)
        self.assertIsNotNone(result["weights"])
        self.assertNotIn("AAPL", result["weights"])
        self.assertIn("MSFT", result["weights"])
        self.assertIn("NVDA", result["weights"])
        self.assertAlmostEqual(sum(result["weights"].values()), 1.0, places=5)

    @patch("data.portfolio.get_stock_history")
    def test_all_tickers_failed_returns_empty_portfolio(self, mock_gsh):
        mock_gsh.return_value = []
        result = optimize_portfolio(["AAPL", "MSFT", "NVDA"], 0.5, 1)
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    @patch("data.portfolio.get_stock_history")
    def test_risk_tolerance_below_zero_is_clamped(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result_clamped = optimize_portfolio(_FOUR_TICKERS, -0.5, 1)
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result_at_zero = optimize_portfolio(_FOUR_TICKERS, 0.0, 1)
        self.assertIsNotNone(result_clamped["weights"])
        self.assertAlmostEqual(sum(result_clamped["weights"].values()), 1.0, places=5)
        for ticker in _FOUR_TICKERS:
            self.assertAlmostEqual(
                result_clamped["weights"][ticker],
                result_at_zero["weights"][ticker],
                places=4,
            )

    @patch("data.portfolio.get_stock_history")
    def test_risk_tolerance_above_one_is_clamped(self, mock_gsh):
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result_clamped = optimize_portfolio(_FOUR_TICKERS, 1.5, 1)
        mock_gsh.side_effect = _FOUR_HISTORIES * 10
        result_at_one = optimize_portfolio(_FOUR_TICKERS, 1.0, 1)
        self.assertIsNotNone(result_clamped["weights"])
        self.assertAlmostEqual(sum(result_clamped["weights"].values()), 1.0, places=5)
        for ticker in _FOUR_TICKERS:
            self.assertAlmostEqual(
                result_clamped["weights"][ticker],
                result_at_one["weights"][ticker],
                places=4,
            )

    def test_horizon_years_zero_returns_empty_portfolio(self):
        result = optimize_portfolio(["AAPL"], 0.5, 0)
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    def test_horizon_years_negative_returns_empty_portfolio(self):
        result = optimize_portfolio(["AAPL"], 0.5, -1)
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    def test_horizon_years_non_numeric_string_returns_empty_portfolio(self):
        result = optimize_portfolio(["AAPL"], 0.5, "bad")
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    @patch("data.portfolio.get_stock_history")
    def test_fewer_than_two_aligned_rows_returns_empty_portfolio(self, mock_gsh):
        mock_gsh.side_effect = [
            _make_history([150.0]),
            _make_history([280.0]),
        ] * 10
        result = optimize_portfolio(["AAPL", "MSFT"], 0.5, 1)
        self.assertIsNone(result["weights"])
        self.assertIsNone(result["expected_return"])
        self.assertIsNone(result["volatility"])
        self.assertIsNone(result["sharpe_ratio"])

    @patch("data.portfolio.get_stock_history")
    def test_zero_volatility_sharpe_is_zero_not_error(self, mock_gsh):
        flat = [100.0] * 300
        mock_gsh.return_value = _make_history(flat)
        result = optimize_portfolio(["AAPL"], 0.5, 1)
        self.assertIsNotNone(result["sharpe_ratio"])
        self.assertEqual(result["sharpe_ratio"], 0.0)
        self.assertIs(type(result["sharpe_ratio"]), float)


if __name__ == "__main__":
    unittest.main()
