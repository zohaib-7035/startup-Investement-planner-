import unittest
from unittest.mock import patch

from data.backtester import (
    _compute_cagr,
    _compute_max_drawdown,
    _compute_sharpe,
    _compute_win_rate,
    run_backtest,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_history(date_close_pairs):
    return [
        {"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 1000}
        for d, c in date_close_pairs
    ]


_HISTORY_3 = _make_history([
    ("2020-01-02", 100.0),
    ("2020-01-03", 110.0),
    ("2020-01-06", 120.0),
])

_SIGNALS_BUY_SELL = [
    {"date": "2020-01-02", "action": "BUY"},
    {"date": "2020-01-06", "action": "SELL"},
]

_RESULT_KEYS = {"cagr", "sharpe_ratio", "max_drawdown", "win_rate", "total_return", "trades", "portfolio_values"}
_METRIC_KEYS = ("cagr", "sharpe_ratio", "max_drawdown", "win_rate", "total_return")


def _assert_empty_result(tc, result):
    for key in _METRIC_KEYS:
        tc.assertIsNone(result[key], msg=f"expected None for {key}")
    tc.assertEqual(result["trades"], [])
    tc.assertEqual(result["portfolio_values"], [])


# ---------------------------------------------------------------------------
# TestOutputSchema
# ---------------------------------------------------------------------------

class TestOutputSchema(unittest.TestCase):

    def _run(self, signals=_SIGNALS_BUY_SELL, history=_HISTORY_3, **kw):
        with patch("data.backtester.get_stock_history", return_value=history):
            return run_backtest(signals, "AAPL", "2020-01-02", "2020-01-06", **kw)

    def test_returns_exactly_seven_keys(self):
        self.assertEqual(set(self._run().keys()), _RESULT_KEYS)

    def test_metric_fields_are_python_float_not_numpy(self):
        result = self._run()
        for key in _METRIC_KEYS:
            self.assertIs(type(result[key]), float, msg=f"{key} is {type(result[key])}, not float")

    def test_trades_is_list_of_dicts_with_required_keys(self):
        result = self._run()
        self.assertIsInstance(result["trades"], list)
        self.assertGreater(len(result["trades"]), 0)
        self.assertEqual(
            set(result["trades"][0].keys()),
            {"entry_date", "exit_date", "entry_price", "exit_price", "shares", "pnl"},
        )

    def test_portfolio_values_is_list_of_dicts_with_date_and_value_keys(self):
        result = self._run()
        self.assertIsInstance(result["portfolio_values"], list)
        self.assertGreater(len(result["portfolio_values"]), 0)
        entry = result["portfolio_values"][0]
        self.assertIn("date", entry)
        self.assertIn("value", entry)
        self.assertIs(type(entry["value"]), float)

    def test_portfolio_values_has_one_entry_per_price_date(self):
        result = self._run()
        self.assertEqual(len(result["portfolio_values"]), len(_HISTORY_3))


# ---------------------------------------------------------------------------
# TestTradeExecution
# ---------------------------------------------------------------------------

class TestTradeExecution(unittest.TestCase):

    def _run(self, signals, history, **kw):
        with patch("data.backtester.get_stock_history", return_value=history):
            return run_backtest(signals, "AAPL", "2020-01-02", "2020-01-06", **kw)

    def _two_day(self, buy_close=100.0, sell_close=110.0, **kw):
        history = _make_history([("2020-01-02", buy_close), ("2020-01-03", sell_close)])
        signals = [{"date": "2020-01-02", "action": "BUY"}, {"date": "2020-01-03", "action": "SELL"}]
        return self._run(signals, history, **kw)

    def test_buy_fill_price_equals_close_times_one_plus_slippage(self):
        result = self._two_day(buy_close=100.0, slippage_pct=0.001)
        self.assertAlmostEqual(result["trades"][0]["entry_price"], 100.0 * 1.001, places=10)

    def test_sell_fill_price_equals_close_times_one_minus_slippage(self):
        result = self._two_day(sell_close=110.0, slippage_pct=0.001)
        self.assertAlmostEqual(result["trades"][0]["exit_price"], 110.0 * 0.999, places=10)

    def test_flat_trade_pnl_is_negative_due_to_costs(self):
        # Same close price for buy and sell — all PnL is eaten by slippage + costs
        result = self._two_day(buy_close=100.0, sell_close=100.0, slippage_pct=0.001, transaction_cost_pct=0.001)
        self.assertLess(result["trades"][0]["pnl"], 0.0)
        self.assertLess(result["total_return"], 0.0)

    def test_shares_is_integer_floor_of_cash_divided_by_fill_price(self):
        # 1050 / (100 * 1.001) = 1050 / 100.1 = 10.489... → 10 shares
        result = self._two_day(buy_close=100.0, initial_capital=1050.0, slippage_pct=0.001, transaction_cost_pct=0.0)
        self.assertEqual(result["trades"][0]["shares"], 10)

    def test_buy_when_already_in_position_is_noop(self):
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 105.0), ("2020-01-06", 110.0)])
        signals = [
            {"date": "2020-01-02", "action": "BUY"},
            {"date": "2020-01-03", "action": "BUY"},  # ignored — already in position
            {"date": "2020-01-06", "action": "SELL"},
        ]
        result = self._run(signals, history)
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(result["trades"][0]["entry_date"], "2020-01-02")

    def test_sell_when_flat_is_noop(self):
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0)])
        signals = [{"date": "2020-01-02", "action": "SELL"}]  # no open position
        result = self._run(signals, history)
        self.assertEqual(result["trades"], [])

    def test_action_strings_are_case_normalised(self):
        # lowercase "buy" / "sell" produce same result as "BUY" / "SELL"
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0)])
        signals = [{"date": "2020-01-02", "action": "buy"}, {"date": "2020-01-03", "action": "sell"}]
        result = self._run(signals, history)
        self.assertEqual(len(result["trades"]), 1)
        self.assertGreater(result["trades"][0]["pnl"], 0.0)


# ---------------------------------------------------------------------------
# TestMetricComputation  (helpers tested directly — no HTTP mock needed)
# ---------------------------------------------------------------------------

class TestMetricComputation(unittest.TestCase):

    def test_cagr_matches_formula_for_known_values(self):
        expected = (11000.0 / 10000.0) ** (365.25 / 365.0) - 1.0
        self.assertAlmostEqual(_compute_cagr(10000.0, 11000.0, 365), expected, places=10)

    def test_cagr_is_zero_when_n_calendar_days_is_zero(self):
        self.assertEqual(_compute_cagr(10000.0, 11000.0, 0), 0.0)

    def test_sharpe_is_zero_when_portfolio_is_completely_flat(self):
        pv = [{"date": f"d{i}", "value": 10000.0} for i in range(5)]
        self.assertEqual(_compute_sharpe(pv), 0.0)

    def test_sharpe_is_zero_when_fewer_than_two_values(self):
        self.assertEqual(_compute_sharpe([{"date": "d1", "value": 10000.0}]), 0.0)

    def test_max_drawdown_correct_for_known_peak_to_trough(self):
        pv = [
            {"date": "d1", "value": 10000.0},
            {"date": "d2", "value": 11000.0},  # peak
            {"date": "d3", "value": 9000.0},   # drawdown = (9000-11000)/11000 = -2/11
            {"date": "d4", "value": 10500.0},
        ]
        self.assertAlmostEqual(_compute_max_drawdown(pv), -2.0 / 11.0, places=10)

    def test_max_drawdown_is_zero_when_portfolio_only_grows(self):
        pv = [{"date": f"d{i}", "value": float(10000 + i * 100)} for i in range(5)]
        self.assertEqual(_compute_max_drawdown(pv), 0.0)

    def test_win_rate_is_correct_fraction_of_profitable_trades(self):
        trades = [{"pnl": 100.0}, {"pnl": -50.0}, {"pnl": 200.0}]
        self.assertAlmostEqual(_compute_win_rate(trades), 2.0 / 3.0, places=10)

    def test_win_rate_is_zero_for_empty_trades_list(self):
        self.assertEqual(_compute_win_rate([]), 0.0)


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def _run(self, signals, history, **kw):
        with patch("data.backtester.get_stock_history", return_value=history):
            return run_backtest(signals, "AAPL", "2020-01-02", "2020-01-06", **kw)

    def test_hold_only_signals_produce_empty_trades_zero_return(self):
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0), ("2020-01-06", 120.0)])
        signals = [{"date": "2020-01-02", "action": "HOLD"}, {"date": "2020-01-03", "action": "HOLD"}]
        result = self._run(signals, history, initial_capital=10000.0)
        self.assertEqual(result["trades"], [])
        self.assertEqual(result["total_return"], 0.0)
        self.assertEqual(result["win_rate"], 0.0)
        for entry in result["portfolio_values"]:
            self.assertAlmostEqual(entry["value"], 10000.0, places=6)

    def test_signal_date_not_in_price_map_is_silently_skipped(self):
        # Saturday 2020-01-04 not in price map
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0)])
        signals = [{"date": "2020-01-04", "action": "BUY"}]
        result = self._run(signals, history, initial_capital=10000.0)
        self.assertEqual(result["trades"], [])
        for entry in result["portfolio_values"]:
            self.assertAlmostEqual(entry["value"], 10000.0, places=6)

    def test_open_position_at_window_end_is_force_liquidated(self):
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0)])
        signals = [{"date": "2020-01-02", "action": "BUY"}]  # no SELL signal
        result = self._run(signals, history)
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(result["trades"][0]["exit_date"], "2020-01-03")

    def test_buy_with_zero_purchasable_shares_is_noop(self):
        # initial=50, fill=100*1.001=100.1 → int(50/100.1) = 0 → no-op
        history = _make_history([("2020-01-02", 100.0), ("2020-01-03", 110.0)])
        signals = [{"date": "2020-01-02", "action": "BUY"}]
        result = self._run(signals, history, initial_capital=50.0)
        self.assertEqual(result["trades"], [])
        for entry in result["portfolio_values"]:
            self.assertAlmostEqual(entry["value"], 50.0, places=6)


# ---------------------------------------------------------------------------
# TestPreflightGuards
# ---------------------------------------------------------------------------

class TestPreflightGuards(unittest.TestCase):

    def _run_with_mock(self, signals, mock_return=_HISTORY_3, mock_side_effect=None, **kw):
        with patch("data.backtester.get_stock_history",
                   return_value=mock_return, side_effect=mock_side_effect):
            return run_backtest(signals, "AAPL", "2020-01-02", "2020-01-06", **kw)

    def test_empty_signals_list_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock([]))

    def test_signals_not_a_list_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock("BUY"))

    def test_negative_initial_capital_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock(_SIGNALS_BUY_SELL, initial_capital=-1000.0))

    def test_zero_initial_capital_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock(_SIGNALS_BUY_SELL, initial_capital=0.0))

    def test_negative_transaction_cost_pct_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock(_SIGNALS_BUY_SELL, transaction_cost_pct=-0.001))

    def test_negative_slippage_pct_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock(_SIGNALS_BUY_SELL, slippage_pct=-0.001))

    def test_get_stock_history_returning_empty_list_returns_empty_result(self):
        _assert_empty_result(self, self._run_with_mock(_SIGNALS_BUY_SELL, mock_return=[]))

    def test_exception_inside_get_stock_history_returns_empty_result(self):
        _assert_empty_result(
            self,
            self._run_with_mock(_SIGNALS_BUY_SELL, mock_return=None, mock_side_effect=RuntimeError("network"))
        )


if __name__ == "__main__":
    unittest.main()
