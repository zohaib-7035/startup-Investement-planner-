import math
import unittest

import pytest

from data.signals import generate_advanced_signal

_BUY_INPUTS = {"adx": 38.0, "atr": 4.2, "momentum": 0.15, "volume_ratio": 1.8}
_SELL_INPUTS = {"adx": 32.0, "atr": 3.1, "momentum": -0.12, "volume_ratio": 1.6}
_WATCHLIST_INPUTS = {"adx": 22.0, "atr": 2.0, "momentum": 0.05, "volume_ratio": 1.1}
_HOLD_INPUTS = {"adx": 15.0, "atr": 1.5, "momentum": 0.02, "volume_ratio": 0.9}


class TestOutputSchema(unittest.TestCase):

    def setUp(self):
        self.result = generate_advanced_signal(**_BUY_INPUTS)

    def test_result_is_dict(self):
        self.assertIsInstance(self.result, dict)
        self.assertGreater(len(self.result), 0)

    def test_result_has_exactly_three_keys(self):
        self.assertEqual(set(self.result.keys()), {"action", "confidence", "reason"})

    def test_action_is_string(self):
        self.assertIsInstance(self.result["action"], str)
        self.assertIn(self.result["action"], {"BUY", "SELL", "HOLD", "WATCHLIST"})

    def test_confidence_is_float(self):
        self.assertIsInstance(self.result["confidence"], float)
        self.assertGreaterEqual(self.result["confidence"], 0.0)
        self.assertLessEqual(self.result["confidence"], 1.0)

    def test_reason_is_non_empty_string(self):
        self.assertIsInstance(self.result["reason"], str)
        self.assertGreater(len(self.result["reason"]), 0)

    def test_invalid_input_returns_dict_with_correct_keys(self):
        result = generate_advanced_signal(adx=None, atr=None, momentum=None, volume_ratio=None)
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), {"action", "confidence", "reason"})

    def test_invalid_input_action_is_valid_string(self):
        result = generate_advanced_signal(adx="bad", atr=2.0, momentum=0.1, volume_ratio=1.5)
        self.assertIn(result["action"], {"BUY", "SELL", "HOLD", "WATCHLIST"})
        self.assertIsInstance(result["confidence"], float)


class TestBuyRule(unittest.TestCase):

    def test_happy_path_returns_buy(self):
        result = generate_advanced_signal(**_BUY_INPUTS)
        self.assertEqual(result["action"], "BUY")

    def test_happy_path_confidence_is_0_85(self):
        result = generate_advanced_signal(**_BUY_INPUTS)
        self.assertEqual(result["confidence"], 0.85)

    def test_happy_path_reason_is_non_empty(self):
        result = generate_advanced_signal(**_BUY_INPUTS)
        self.assertIn("ADX", result["reason"])
        self.assertIn("momentum", result["reason"])

    def test_adx_exactly_25_does_not_trigger_buy(self):
        result = generate_advanced_signal(adx=25.0, atr=2.0, momentum=0.05, volume_ratio=1.5)
        self.assertNotEqual(result["action"], "BUY")
        self.assertEqual(result["action"], "WATCHLIST")

    def test_boundary_adx_26_returns_buy(self):
        result = generate_advanced_signal(adx=26.0, atr=2.0, momentum=0.05, volume_ratio=1.5)
        self.assertEqual(result["action"], "BUY")

    def test_volume_ratio_exactly_1_5_triggers_buy(self):
        result = generate_advanced_signal(adx=30.0, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["action"], "BUY")

    def test_high_atr_reduces_buy_confidence_by_10_percent(self):
        result = generate_advanced_signal(adx=38.0, atr=6.5, momentum=0.15, volume_ratio=1.8)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["confidence"], pytest.approx(0.765, rel=1e-9))

    def test_high_atr_buy_confidence_is_not_base_0_85(self):
        result = generate_advanced_signal(adx=38.0, atr=6.5, momentum=0.15, volume_ratio=1.8)
        self.assertNotAlmostEqual(result["confidence"], 0.85, places=6)


class TestSellRule(unittest.TestCase):

    def test_happy_path_returns_sell(self):
        result = generate_advanced_signal(**_SELL_INPUTS)
        self.assertEqual(result["action"], "SELL")

    def test_happy_path_confidence_is_0_75(self):
        result = generate_advanced_signal(**_SELL_INPUTS)
        self.assertEqual(result["confidence"], 0.75)

    def test_happy_path_reason_is_non_empty(self):
        result = generate_advanced_signal(**_SELL_INPUTS)
        self.assertIn("ADX", result["reason"])
        self.assertIn("momentum", result["reason"])

    def test_zero_momentum_with_sell_conditions_falls_to_hold(self):
        result = generate_advanced_signal(adx=32.0, atr=2.0, momentum=0.0, volume_ratio=1.6)
        self.assertNotEqual(result["action"], "SELL")
        self.assertEqual(result["action"], "HOLD")

    def test_high_atr_reduces_sell_confidence_by_10_percent(self):
        result = generate_advanced_signal(adx=32.0, atr=7.0, momentum=-0.12, volume_ratio=1.6)
        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["confidence"], pytest.approx(0.675, rel=1e-9))

    def test_high_atr_sell_confidence_is_not_base_0_75(self):
        result = generate_advanced_signal(adx=32.0, atr=7.0, momentum=-0.12, volume_ratio=1.6)
        self.assertNotAlmostEqual(result["confidence"], 0.75, places=6)


class TestWatchlistRule(unittest.TestCase):

    def test_happy_path_returns_watchlist(self):
        result = generate_advanced_signal(**_WATCHLIST_INPUTS)
        self.assertEqual(result["action"], "WATCHLIST")

    def test_happy_path_confidence_is_0_55(self):
        result = generate_advanced_signal(**_WATCHLIST_INPUTS)
        self.assertEqual(result["confidence"], 0.55)

    def test_happy_path_reason_is_non_empty(self):
        result = generate_advanced_signal(**_WATCHLIST_INPUTS)
        self.assertIn("ADX", result["reason"])
        self.assertIn("20", result["reason"])

    def test_adx_25_boundary_returns_watchlist_not_buy(self):
        result = generate_advanced_signal(adx=25.0, atr=2.0, momentum=0.05, volume_ratio=1.5)
        self.assertEqual(result["action"], "WATCHLIST")

    def test_adx_20_lower_boundary_returns_watchlist(self):
        result = generate_advanced_signal(adx=20.0, atr=2.0, momentum=0.05, volume_ratio=1.1)
        self.assertEqual(result["action"], "WATCHLIST")

    def test_high_atr_applies_penalty_to_watchlist_confidence(self):
        result = generate_advanced_signal(adx=22.0, atr=6.0, momentum=0.05, volume_ratio=1.1)
        self.assertEqual(result["action"], "WATCHLIST")
        self.assertEqual(result["confidence"], pytest.approx(0.495, rel=1e-9))


class TestHoldRule(unittest.TestCase):

    def test_happy_path_returns_hold(self):
        result = generate_advanced_signal(**_HOLD_INPUTS)
        self.assertEqual(result["action"], "HOLD")

    def test_happy_path_confidence_is_0_40(self):
        result = generate_advanced_signal(**_HOLD_INPUTS)
        self.assertEqual(result["confidence"], 0.40)

    def test_happy_path_reason_is_non_empty(self):
        result = generate_advanced_signal(**_HOLD_INPUTS)
        self.assertIn("ADX", result["reason"])
        self.assertIn("momentum", result["reason"])

    def test_adx_below_20_returns_hold(self):
        result = generate_advanced_signal(adx=19.9, atr=2.0, momentum=0.10, volume_ratio=2.0)
        self.assertEqual(result["action"], "HOLD")

    def test_momentum_zero_with_high_adx_and_volume_falls_to_hold(self):
        result = generate_advanced_signal(adx=30.0, atr=2.0, momentum=0.0, volume_ratio=1.8)
        self.assertEqual(result["action"], "HOLD")

    def test_volume_ratio_below_1_5_prevents_buy_falls_to_hold(self):
        result = generate_advanced_signal(adx=30.0, atr=2.0, momentum=0.10, volume_ratio=1.4)
        self.assertEqual(result["action"], "HOLD")


class TestAtrModifier(unittest.TestCase):

    def test_atr_exactly_5_0_produces_no_penalty(self):
        result = generate_advanced_signal(adx=38.0, atr=5.0, momentum=0.15, volume_ratio=1.8)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["confidence"], 0.85)

    def test_atr_above_5_0_reduces_confidence(self):
        result = generate_advanced_signal(adx=38.0, atr=5.01, momentum=0.15, volume_ratio=1.8)
        self.assertEqual(result["action"], "BUY")
        self.assertLess(result["confidence"], 0.85)

    def test_atr_5_01_confidence_is_approx_0_765(self):
        result = generate_advanced_signal(adx=38.0, atr=5.01, momentum=0.15, volume_ratio=1.8)
        self.assertEqual(result["confidence"], pytest.approx(0.765, rel=1e-9))

    def test_atr_none_triggers_invalid_input_fallback(self):
        result = generate_advanced_signal(adx=38.0, atr=None, momentum=0.15, volume_ratio=1.8)
        self.assertEqual(result["confidence"], 0.0)


class TestPreflightGuard(unittest.TestCase):

    def test_adx_none_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=None, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_atr_none_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=38.0, atr=None, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_momentum_none_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=38.0, atr=2.0, momentum=None, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_volume_ratio_none_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=38.0, atr=2.0, momentum=0.10, volume_ratio=None)
        self.assertEqual(result["confidence"], 0.0)

    def test_none_input_does_not_raise(self):
        try:
            generate_advanced_signal(adx=None, atr=None, momentum=None, volume_ratio=None)
        except Exception as exc:
            self.fail(f"generate_advanced_signal raised unexpectedly: {exc}")

    def test_negative_adx_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=-1.0, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_adx_above_100_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=101.0, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_non_numeric_string_adx_returns_confidence_zero(self):
        result = generate_advanced_signal(adx="strong", atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_nan_adx_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=math.nan, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_infinity_adx_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=math.inf, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_negative_volume_ratio_returns_confidence_zero(self):
        result = generate_advanced_signal(adx=38.0, atr=2.0, momentum=0.10, volume_ratio=-0.5)
        self.assertEqual(result["confidence"], 0.0)

    def test_fallback_action_is_hold(self):
        result = generate_advanced_signal(adx=None, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertEqual(result["action"], "HOLD")

    def test_fallback_reason_is_non_empty(self):
        result = generate_advanced_signal(adx=None, atr=2.0, momentum=0.10, volume_ratio=1.5)
        self.assertIn("Invalid", result["reason"])
        self.assertIn("validation", result["reason"])
