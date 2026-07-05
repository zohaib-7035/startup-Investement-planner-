import json
import unittest
from unittest.mock import MagicMock, patch

from data.scenario import simulate_scenario

_VALID_PAYLOAD = {
    "directly_affected_sectors": ["Semiconductors", "Technology Hardware"],
    "indirectly_affected_sectors": ["Automotive", "Consumer Electronics"],
    "impacted_companies": [
        {"name": "NVIDIA Corporation", "ticker": "NVDA", "impact_type": "Negative"},
        {"name": "Advanced Micro Devices", "ticker": "AMD", "impact_type": "Negative"},
    ],
    "severity_level": "HIGH",
    "reasoning_chain": [
        "US export restrictions prohibit sale of advanced chips to China.",
        "NVIDIA loses significant China data-centre revenue.",
        "AMD faces similar restrictions impacting GPU sales.",
    ],
    "confidence_score": 0.82,
}

_VALID_RESPONSE = json.dumps(_VALID_PAYLOAD)
_FENCED_RESPONSE = f"```json\n{_VALID_RESPONSE}\n```"
_MALFORMED_RESPONSE = "{ this is not valid json }"

_EVENT = "United States introduces new semiconductor export restrictions to China."


def _mock_post(response_text):
    """Build a mock requests.Response that returns `response_text` from Ollama."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": response_text}}
    return mock_resp


@patch("data.scenario.requests.post")
class TestOutputSchema(unittest.TestCase):

    def test_result_is_dict(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_result_has_exactly_six_keys(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertEqual(len(result), 6)

    def test_key_names_are_correct(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        expected = {
            "directly_affected_sectors", "indirectly_affected_sectors",
            "impacted_companies", "severity_level", "reasoning_chain", "confidence_score",
        }
        self.assertEqual(set(result.keys()), expected)

    def test_directly_affected_sectors_is_list(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIsInstance(result["directly_affected_sectors"], list)

    def test_impacted_companies_is_list(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIsInstance(result["impacted_companies"], list)

    def test_confidence_score_is_float(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIsInstance(result["confidence_score"], float)
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)


@patch("data.scenario.requests.post")
class TestHappyPath(unittest.TestCase):

    def test_directly_affected_sectors_is_non_empty(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertGreater(len(result["directly_affected_sectors"]), 0)
        self.assertIsInstance(result["directly_affected_sectors"][0], str)

    def test_directly_affected_sectors_contains_expected_value(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIn("Semiconductors", result["directly_affected_sectors"])

    def test_impacted_companies_first_item_has_name_key(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIn("name", result["impacted_companies"][0])
        self.assertIsInstance(result["impacted_companies"][0]["name"], str)

    def test_impacted_companies_first_item_has_ticker_key(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIn("ticker", result["impacted_companies"][0])

    def test_impacted_companies_first_item_has_impact_type_key(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIn("impact_type", result["impacted_companies"][0])

    def test_reasoning_chain_is_non_empty(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertGreater(len(result["reasoning_chain"]), 0)
        self.assertIsInstance(result["reasoning_chain"][0], str)

    def test_severity_level_is_in_valid_set(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertIn(result["severity_level"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})


def _response_with_severity(severity_str):
    payload = dict(_VALID_PAYLOAD)
    payload["severity_level"] = severity_str
    return json.dumps(payload)


@patch("data.scenario.requests.post")
class TestSeverityNormalisation(unittest.TestCase):

    def test_lowercase_high_normalised_to_HIGH(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_severity("high"))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["severity_level"], "HIGH")

    def test_mixed_case_critical_normalised(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_severity("Critical"))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["severity_level"], "CRITICAL")

    def test_unknown_severe_defaults_to_medium(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_severity("Severe"))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["severity_level"], "MEDIUM")

    def test_all_four_valid_severity_levels_accepted(self, mock_post):
        for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            mock_post.return_value = _mock_post(_response_with_severity(level))
            result = simulate_scenario(_EVENT)
            self.assertEqual(result["severity_level"], level)


def _response_with_confidence(confidence_val):
    payload = dict(_VALID_PAYLOAD)
    payload["confidence_score"] = confidence_val
    return json.dumps(payload)


@patch("data.scenario.requests.post")
class TestConfidenceClamping(unittest.TestCase):

    def test_confidence_above_one_clamped_to_one(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_confidence(1.5))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 1.0)

    def test_confidence_below_zero_clamped_to_zero(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_confidence(-0.2))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)

    def test_confidence_zero_exact(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_confidence(0.0))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)

    def test_confidence_one_exact(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_confidence(1.0))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 1.0)

    def test_integer_confidence_returns_float(self, mock_post):
        mock_post.return_value = _mock_post(_response_with_confidence(1))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 1.0)
        self.assertIsInstance(result["confidence_score"], float)


@patch("data.scenario.requests.post")
class TestFenceStripping(unittest.TestCase):

    def test_fenced_json_parsed_correctly(self, mock_post):
        mock_post.return_value = _mock_post(_FENCED_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertGreater(len(result["directly_affected_sectors"]), 0)
        self.assertNotEqual(result["confidence_score"], 0.0)

    def test_plain_json_also_parsed_correctly(self, mock_post):
        mock_post.return_value = _mock_post(_VALID_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertGreater(len(result["directly_affected_sectors"]), 0)
        self.assertNotEqual(result["confidence_score"], 0.0)


@patch("data.scenario.requests.post")
class TestPreflightGuard(unittest.TestCase):

    def test_none_input_returns_confidence_zero(self, mock_post):
        result = simulate_scenario(None)
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertIsInstance(result, dict)

    def test_empty_string_returns_confidence_zero(self, mock_post):
        result = simulate_scenario("")
        self.assertEqual(result["confidence_score"], 0.0)

    def test_whitespace_input_returns_confidence_zero(self, mock_post):
        result = simulate_scenario("   ")
        self.assertEqual(result["confidence_score"], 0.0)

    def test_none_input_does_not_raise(self, mock_post):
        try:
            simulate_scenario(None)
        except Exception as exc:
            self.fail(f"simulate_scenario raised unexpectedly: {exc}")

    def test_empty_string_does_not_raise(self, mock_post):
        try:
            simulate_scenario("")
        except Exception as exc:
            self.fail(f"simulate_scenario raised unexpectedly: {exc}")

    def test_none_input_makes_no_api_call(self, mock_post):
        simulate_scenario(None)
        mock_post.assert_not_called()


@patch("data.scenario.requests.post")
class TestLlmFailure(unittest.TestCase):

    def test_malformed_json_returns_empty_result(self, mock_post):
        mock_post.return_value = _mock_post(_MALFORMED_RESPONSE)
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertEqual(result["directly_affected_sectors"], [])

    def test_ollama_unavailable_returns_empty_result(self, mock_post):
        mock_post.side_effect = RuntimeError("Connection refused — Ollama not running")
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertEqual(result["severity_level"], "MEDIUM")

    def test_json_list_response_returns_empty_result(self, mock_post):
        mock_post.return_value = _mock_post(json.dumps([{"key": "value"}]))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertEqual(result["impacted_companies"], [])

    def test_empty_directly_affected_sectors_returns_empty_result(self, mock_post):
        payload = dict(_VALID_PAYLOAD)
        payload["directly_affected_sectors"] = []
        mock_post.return_value = _mock_post(json.dumps(payload))
        result = simulate_scenario(_EVENT)
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertEqual(result["directly_affected_sectors"], [])


if __name__ == "__main__":
    unittest.main()
