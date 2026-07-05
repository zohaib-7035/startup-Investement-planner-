import unittest
from data.meta_agent import aggregate_signals

_STANDARD_INPUT = {
    "technical": {"action": "BUY", "confidence": 0.85},
    "fundamentals": {"action": "BUY", "confidence": 0.90},
    "sentiment": {"action": "SELL", "confidence": 0.65},
    "macro": {"action": "HOLD", "confidence": 0.70},
    "risk": {"level": "HIGH"},
}
# BUY total=1.75, SELL=0.65, HOLD=0.70 → winner BUY
# winning mean = (0.85+0.90)/2 = 0.875; penalty 0.80 → confidence 0.70
# conflicts: sentiment(SELL), macro(HOLD) — 2 entries

_ALL_BUY = {
    "technical": {"action": "BUY", "confidence": 0.80},
    "fundamentals": {"action": "BUY", "confidence": 0.85},
    "sentiment": {"action": "BUY", "confidence": 0.70},
    "macro": {"action": "BUY", "confidence": 0.75},
    "risk": {"level": "LOW"},
}
# mean BUY = (0.80+0.85+0.70+0.75)/4 = 0.775; no penalty; no conflicts

_ALL_BUY_RISK_BASE = {
    "technical": {"action": "BUY", "confidence": 0.80},
    "fundamentals": {"action": "BUY", "confidence": 0.70},
    "sentiment": {"action": "BUY", "confidence": 0.80},
    "macro": {"action": "BUY", "confidence": 0.70},
}
# mean BUY = (0.80+0.70+0.80+0.70)/4 = 0.75; penalty depends on risk level

_TIE_INPUT = {
    "technical": {"action": "BUY", "confidence": 0.80},
    "fundamentals": {"action": "BUY", "confidence": 0.70},
    "sentiment": {"action": "SELL", "confidence": 0.80},
    "macro": {"action": "SELL", "confidence": 0.70},
    "risk": {"level": "LOW"},
}
# BUY total=1.50, SELL total=1.50 — exact tie → HOLD; all 4 agents in conflicts


class TestOutputSchema(unittest.TestCase):
    def _result(self):
        return aggregate_signals(_STANDARD_INPUT)

    def test_returns_final_action_key(self):
        result = self._result()
        self.assertIn("final_action", result)
        self.assertIsInstance(result["final_action"], str)

    def test_returns_confidence_key(self):
        result = self._result()
        self.assertIn("confidence", result)
        self.assertIs(type(result["confidence"]), float)

    def test_returns_reasoning_key(self):
        result = self._result()
        self.assertIn("reasoning", result)
        self.assertIsInstance(result["reasoning"], str)

    def test_returns_conflicts_key(self):
        result = self._result()
        self.assertIn("conflicts", result)
        self.assertIsInstance(result["conflicts"], list)

    def test_confidence_is_native_float_not_int(self):
        result = self._result()
        self.assertIs(type(result["confidence"]), float)
        self.assertGreater(result["confidence"], 0.0)

    def test_final_action_is_one_of_three_valid_values(self):
        result = self._result()
        self.assertIn(result["final_action"], {"BUY", "SELL", "HOLD"})

    def test_reasoning_is_nonempty_string(self):
        result = self._result()
        self.assertIsInstance(result["reasoning"], str)
        self.assertGreater(len(result["reasoning"]), 0)

    def test_reasoning_mentions_all_four_agents(self):
        result = self._result()
        for agent in ("technical", "fundamentals", "sentiment", "macro"):
            self.assertIn(agent, result["reasoning"])

    def test_none_input_has_all_four_keys(self):
        result = aggregate_signals(None)
        for key in ("final_action", "confidence", "reasoning", "conflicts"):
            self.assertIn(key, result)

    def test_empty_dict_has_all_four_keys(self):
        result = aggregate_signals({})
        for key in ("final_action", "confidence", "reasoning", "conflicts"):
            self.assertIn(key, result)

    def test_non_dict_has_all_four_keys(self):
        result = aggregate_signals(42)
        for key in ("final_action", "confidence", "reasoning", "conflicts"):
            self.assertIn(key, result)

    def test_all_invalid_agents_has_all_four_keys(self):
        bad = {
            "technical": "not-a-dict",
            "fundamentals": None,
            "sentiment": {"action": "MAYBE", "confidence": 0.5},
            "macro": {"action": "BUY", "confidence": 999},
            "risk": {"level": "HIGH"},
        }
        result = aggregate_signals(bad)
        for key in ("final_action", "confidence", "reasoning", "conflicts"):
            self.assertIn(key, result)


class TestVotingOutcome(unittest.TestCase):
    def test_all_buy_returns_buy(self):
        result = aggregate_signals(_ALL_BUY)
        self.assertEqual(result["final_action"], "BUY")
        self.assertEqual(result["conflicts"], [])

    def test_all_buy_confidence_is_mean(self):
        result = aggregate_signals(_ALL_BUY)
        expected = (0.80 + 0.85 + 0.70 + 0.75) / 4
        self.assertAlmostEqual(result["confidence"], expected, places=10)

    def test_majority_buy_wins(self):
        inp = {
            "technical": {"action": "BUY", "confidence": 0.80},
            "fundamentals": {"action": "BUY", "confidence": 0.90},
            "sentiment": {"action": "BUY", "confidence": 0.75},
            "macro": {"action": "SELL", "confidence": 0.65},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        self.assertEqual(len(result["conflicts"]), 1)

    def test_majority_sell_wins(self):
        inp = {
            "technical": {"action": "SELL", "confidence": 0.85},
            "fundamentals": {"action": "SELL", "confidence": 0.80},
            "sentiment": {"action": "SELL", "confidence": 0.75},
            "macro": {"action": "BUY", "confidence": 0.90},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "SELL")
        self.assertEqual(len(result["conflicts"]), 1)

    def test_standard_example_winner_is_buy(self):
        result = aggregate_signals(_STANDARD_INPUT)
        self.assertEqual(result["final_action"], "BUY")

    def test_none_input_returns_hold(self):
        result = aggregate_signals(None)
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_empty_dict_returns_hold(self):
        result = aggregate_signals({})
        self.assertEqual(result["final_action"], "HOLD")
        self.assertIsInstance(result["conflicts"], list)

    def test_non_dict_input_returns_hold(self):
        result = aggregate_signals(["BUY", "SELL"])
        self.assertEqual(result["final_action"], "HOLD")
        self.assertIs(type(result["confidence"]), float)

    def test_all_invalid_agents_returns_hold(self):
        bad = {k: "invalid" for k in ("technical", "fundamentals", "sentiment", "macro")}
        result = aggregate_signals(bad)
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)


class TestRiskPenalty(unittest.TestCase):
    def _buy_inp(self, risk_level=None):
        inp = dict(_ALL_BUY_RISK_BASE)
        if risk_level is not None:
            inp["risk"] = {"level": risk_level}
        return inp

    def test_standard_example_confidence(self):
        result = aggregate_signals(_STANDARD_INPUT)
        expected = (0.85 + 0.90) / 2 * 0.80
        self.assertAlmostEqual(result["confidence"], expected, places=10)
        self.assertIs(type(result["confidence"]), float)

    def test_high_penalty_applied(self):
        result = aggregate_signals(self._buy_inp("HIGH"))
        expected = 0.75 * 0.80
        self.assertAlmostEqual(result["confidence"], expected, places=10)

    def test_critical_penalty_applied(self):
        result = aggregate_signals(self._buy_inp("CRITICAL"))
        expected = 0.75 * 0.60
        self.assertAlmostEqual(result["confidence"], expected, places=10)

    def test_low_risk_no_penalty(self):
        result = aggregate_signals(self._buy_inp("LOW"))
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)

    def test_medium_risk_no_penalty(self):
        result = aggregate_signals(self._buy_inp("MEDIUM"))
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)

    def test_confidence_clamped_within_range(self):
        result = aggregate_signals(self._buy_inp("LOW"))
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_unknown_risk_level_no_penalty(self):
        result = aggregate_signals(self._buy_inp("EXTREME"))
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)

    def test_missing_risk_key_no_penalty(self):
        result = aggregate_signals(dict(_ALL_BUY_RISK_BASE))
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)

    def test_risk_not_a_dict_no_penalty(self):
        inp = dict(_ALL_BUY_RISK_BASE)
        inp["risk"] = "HIGH"
        result = aggregate_signals(inp)
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)

    def test_none_risk_level_no_penalty(self):
        inp = dict(_ALL_BUY_RISK_BASE)
        inp["risk"] = {"level": None}
        result = aggregate_signals(inp)
        self.assertAlmostEqual(result["confidence"], 0.75, places=10)


class TestTieBreaking(unittest.TestCase):
    def test_exact_tie_returns_hold(self):
        result = aggregate_signals(_TIE_INPUT)
        self.assertEqual(result["final_action"], "HOLD")

    def test_exact_tie_buy_agents_in_conflicts(self):
        result = aggregate_signals(_TIE_INPUT)
        conflicts_text = " ".join(result["conflicts"])
        self.assertIn("BUY", conflicts_text)
        self.assertGreater(len(result["conflicts"]), 0)

    def test_exact_tie_sell_agents_in_conflicts(self):
        result = aggregate_signals(_TIE_INPUT)
        conflicts_text = " ".join(result["conflicts"])
        self.assertIn("SELL", conflicts_text)

    def test_exact_tie_all_four_agents_conflict(self):
        result = aggregate_signals(_TIE_INPUT)
        self.assertEqual(len(result["conflicts"]), 4)

    def test_no_tie_when_buy_leads(self):
        inp = {
            "technical": {"action": "BUY", "confidence": 0.90},
            "fundamentals": {"action": "BUY", "confidence": 0.85},
            "sentiment": {"action": "SELL", "confidence": 0.80},
            "macro": {"action": "SELL", "confidence": 0.70},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        self.assertNotEqual(result["final_action"], "HOLD")

    def test_no_tie_when_sell_leads(self):
        inp = {
            "technical": {"action": "SELL", "confidence": 0.90},
            "fundamentals": {"action": "SELL", "confidence": 0.85},
            "sentiment": {"action": "BUY", "confidence": 0.80},
            "macro": {"action": "BUY", "confidence": 0.70},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "SELL")
        self.assertNotEqual(result["final_action"], "HOLD")

    def test_hold_wins_outright_when_highest_weight(self):
        inp = {
            "technical": {"action": "HOLD", "confidence": 0.90},
            "fundamentals": {"action": "HOLD", "confidence": 0.85},
            "sentiment": {"action": "BUY", "confidence": 0.60},
            "macro": {"action": "SELL", "confidence": 0.60},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "HOLD")

    def test_no_tie_when_buy_weight_is_zero(self):
        inp = {
            "technical": {"action": "HOLD", "confidence": 0.70},
            "fundamentals": {"action": "HOLD", "confidence": 0.80},
            "sentiment": {"action": "SELL", "confidence": 0.75},
            "macro": {"action": "SELL", "confidence": 0.65},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertNotEqual(result["final_action"], "BUY")
        self.assertIn(result["final_action"], {"SELL", "HOLD"})


class TestConflictDetection(unittest.TestCase):
    def test_3buy_1sell_one_conflict(self):
        inp = {
            "technical": {"action": "BUY", "confidence": 0.80},
            "fundamentals": {"action": "BUY", "confidence": 0.85},
            "sentiment": {"action": "SELL", "confidence": 0.65},
            "macro": {"action": "BUY", "confidence": 0.75},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertIn("sentiment", result["conflicts"][0])

    def test_standard_example_two_conflicts(self):
        result = aggregate_signals(_STANDARD_INPUT)
        self.assertEqual(len(result["conflicts"]), 2)

    def test_conflict_string_contains_agent_name(self):
        inp = {
            "technical": {"action": "BUY", "confidence": 0.80},
            "fundamentals": {"action": "BUY", "confidence": 0.85},
            "sentiment": {"action": "SELL", "confidence": 0.65},
            "macro": {"action": "BUY", "confidence": 0.75},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertIn("sentiment", result["conflicts"][0])

    def test_conflict_string_contains_dissenting_action(self):
        inp = {
            "technical": {"action": "BUY", "confidence": 0.80},
            "fundamentals": {"action": "BUY", "confidence": 0.85},
            "sentiment": {"action": "SELL", "confidence": 0.65},
            "macro": {"action": "BUY", "confidence": 0.75},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertIn("SELL", result["conflicts"][0])

    def test_hold_dissenters_appear_in_conflicts(self):
        result = aggregate_signals(_STANDARD_INPUT)
        conflicts_text = " ".join(result["conflicts"])
        self.assertIn("macro", conflicts_text)
        self.assertIn("HOLD", conflicts_text)

    def test_all_agree_no_conflicts(self):
        result = aggregate_signals(_ALL_BUY)
        self.assertEqual(result["conflicts"], [])
        self.assertIsInstance(result["conflicts"], list)

    def test_none_input_conflicts_is_empty_list(self):
        result = aggregate_signals(None)
        self.assertIsInstance(result["conflicts"], list)
        self.assertEqual(len(result["conflicts"]), 0)

    def test_empty_dict_conflicts_is_empty_list(self):
        result = aggregate_signals({})
        self.assertIsInstance(result["conflicts"], list)
        self.assertEqual(len(result["conflicts"]), 0)

    def test_tie_all_four_agents_in_conflicts(self):
        result = aggregate_signals(_TIE_INPUT)
        self.assertEqual(len(result["conflicts"]), 4)
        self.assertIsInstance(result["conflicts"], list)


class TestPreflightGuard(unittest.TestCase):
    def test_none_returns_hold(self):
        result = aggregate_signals(None)
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_int_input_returns_hold(self):
        result = aggregate_signals(42)
        self.assertEqual(result["final_action"], "HOLD")
        self.assertIsInstance(result["conflicts"], list)

    def test_list_input_returns_hold(self):
        result = aggregate_signals(["BUY", "SELL"])
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_string_input_returns_hold(self):
        result = aggregate_signals("BUY")
        self.assertEqual(result["final_action"], "HOLD")
        self.assertIs(type(result["confidence"]), float)

    def test_empty_dict_returns_hold(self):
        result = aggregate_signals({})
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)

    def test_only_risk_key_present_returns_hold(self):
        result = aggregate_signals({"risk": {"level": "HIGH"}})
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["conflicts"], [])

    def test_never_raises_on_none(self):
        try:
            result = aggregate_signals(None)
            self.assertIn("final_action", result)
        except Exception as exc:
            self.fail(f"aggregate_signals raised on None: {exc}")

    def test_never_raises_on_int(self):
        try:
            result = aggregate_signals(99)
            self.assertIn("final_action", result)
        except Exception as exc:
            self.fail(f"aggregate_signals raised on int: {exc}")

    def test_never_raises_on_arbitrary_object(self):
        try:
            result = aggregate_signals(object())
            self.assertIn("final_action", result)
        except Exception as exc:
            self.fail(f"aggregate_signals raised on object(): {exc}")


class TestInvalidEntrySkip(unittest.TestCase):
    def _all_buy(self):
        return {
            "technical": {"action": "BUY", "confidence": 0.80},
            "fundamentals": {"action": "BUY", "confidence": 0.90},
            "sentiment": {"action": "BUY", "confidence": 0.70},
            "macro": {"action": "BUY", "confidence": 0.60},
            "risk": {"level": "LOW"},
        }

    def test_confidence_above_one_skipped(self):
        inp = self._all_buy()
        inp["macro"] = {"action": "BUY", "confidence": 1.5}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        expected = (0.80 + 0.90 + 0.70) / 3
        self.assertAlmostEqual(result["confidence"], expected, places=10)

    def test_confidence_below_zero_skipped(self):
        inp = self._all_buy()
        inp["macro"] = {"action": "BUY", "confidence": -0.1}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        expected = (0.80 + 0.90 + 0.70) / 3
        self.assertAlmostEqual(result["confidence"], expected, places=10)

    def test_action_unknown_skipped(self):
        inp = self._all_buy()
        inp["macro"] = {"action": "MAYBE", "confidence": 0.80}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        self.assertEqual(result["confidence"], (0.80 + 0.90 + 0.70) / 3)

    def test_action_non_string_skipped(self):
        inp = self._all_buy()
        inp["macro"] = {"action": 1, "confidence": 0.80}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")

    def test_confidence_string_skipped(self):
        inp = self._all_buy()
        inp["macro"] = {"action": "BUY", "confidence": "high"}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        self.assertGreater(result["confidence"], 0.0)

    def test_non_dict_agent_skipped(self):
        inp = self._all_buy()
        inp["macro"] = "not-a-dict"
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")
        self.assertIs(type(result["confidence"]), float)

    def test_confidence_zero_boundary_is_valid(self):
        inp = self._all_buy()
        inp["macro"] = {"action": "SELL", "confidence": 0.0}
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")

    def test_confidence_one_boundary_is_valid(self):
        inp = {
            "technical": {"action": "SELL", "confidence": 1.0},
            "fundamentals": {"action": "BUY", "confidence": 0.50},
            "sentiment": {"action": "BUY", "confidence": 0.60},
            "macro": {"action": "BUY", "confidence": 0.70},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(inp)
        self.assertEqual(result["final_action"], "BUY")

    def test_all_agents_invalid_returns_hold(self):
        bad = {
            "technical": {"action": "BUY", "confidence": 2.0},
            "fundamentals": {"action": "MAYBE", "confidence": 0.80},
            "sentiment": "not-a-dict",
            "macro": {"action": "BUY", "confidence": -0.5},
            "risk": {"level": "LOW"},
        }
        result = aggregate_signals(bad)
        self.assertEqual(result["final_action"], "HOLD")
        self.assertEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
