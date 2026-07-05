import unittest

from data.screener import generate_recommendation


class TestGenerateRecommendation(unittest.TestCase):

    def test_buy_rule_fires_when_rsi_oversold_and_eps_positive(self):
        result = generate_recommendation(rsi=25, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "BUY")
        self.assertEqual(result["confidence"], 0.85)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_sell_rule_fires_when_rsi_overbought(self):
        result = generate_recommendation(rsi=75, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["confidence"], 0.75)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_hold_when_no_rule_fires(self):
        result = generate_recommendation(rsi=50, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_buy_blocked_when_eps_surprise_is_none(self):
        result = generate_recommendation(rsi=25, eps_surprise=None, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)

    def test_buy_blocked_when_eps_surprise_is_negative(self):
        result = generate_recommendation(rsi=25, eps_surprise=-0.10, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)

    def test_buy_blocked_when_eps_surprise_is_exactly_zero(self):
        result = generate_recommendation(rsi=25, eps_surprise=0.0, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)

    def test_sell_fires_when_rsi_overbought_despite_positive_eps(self):
        result = generate_recommendation(rsi=75, eps_surprise=0.10, pe_ratio=20)
        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["confidence"], 0.75)

    def test_sell_fires_when_eps_surprise_and_pe_ratio_are_none(self):
        result = generate_recommendation(rsi=75, eps_surprise=None, pe_ratio=None)
        self.assertEqual(result["action"], "SELL")
        self.assertEqual(result["confidence"], 0.75)

    def test_rsi_boundary_30_does_not_trigger_buy(self):
        result = generate_recommendation(rsi=30, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)

    def test_rsi_boundary_70_does_not_trigger_sell(self):
        result = generate_recommendation(rsi=70, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.50)

    def test_none_rsi_returns_invalid_input_hold_with_zero_confidence(self):
        result = generate_recommendation(rsi=None, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_string_rsi_returns_invalid_input_hold(self):
        result = generate_recommendation(rsi="high", eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_negative_rsi_returns_invalid_input_hold(self):
        result = generate_recommendation(rsi=-5, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_rsi_above_100_returns_invalid_input_hold(self):
        result = generate_recommendation(rsi=105, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_returned_dict_has_exactly_three_keys(self):
        result = generate_recommendation(rsi=50, eps_surprise=0.0, pe_ratio=20)
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result.keys()), {"action", "confidence", "reason"})

    def test_confidence_is_always_python_float(self):
        cases = [(25, 0.05), (75, None), (50, 0.0), (None, 0.05)]
        for rsi, eps in cases:
            result = generate_recommendation(rsi=rsi, eps_surprise=eps, pe_ratio=15)
            self.assertIs(
                type(result["confidence"]), float,
                f"confidence should be float for rsi={rsi}, eps_surprise={eps}",
            )

    def test_action_confidence_consistency_across_all_actions(self):
        expected = {"BUY": 0.85, "SELL": 0.75, "HOLD": 0.50}
        buy = generate_recommendation(rsi=25, eps_surprise=0.05, pe_ratio=15)
        self.assertEqual(buy["confidence"], expected[buy["action"]])
        sell = generate_recommendation(rsi=75, eps_surprise=None, pe_ratio=None)
        self.assertEqual(sell["confidence"], expected[sell["action"]])
        hold = generate_recommendation(rsi=50, eps_surprise=None, pe_ratio=None)
        self.assertEqual(hold["confidence"], expected[hold["action"]])


if __name__ == "__main__":
    unittest.main()
