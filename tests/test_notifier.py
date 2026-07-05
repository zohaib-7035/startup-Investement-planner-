import os
import unittest
from unittest.mock import MagicMock, call, patch

import requests

from data.notifier import send_alert


_VALID_PAYLOAD = {
    "ticker": "TSLA",
    "signal": "SELL",
    "severity": "HIGH",
    "reason": "Earnings miss and reduced forward guidance",
}

_VALID_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:ABCxyz",
    "TELEGRAM_CHAT_ID": "-100123456789",
}

_SUCCESS_BODY = {"ok": True, "result": {"message_id": 42}}


def _api_resp(status_code, body=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = body if body is not None else {}
    return mock


class TestSendAlertSchema(unittest.TestCase):
    """Result dict always has exactly 4 keys with correct types, across all outcome paths."""

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_result_has_exactly_four_keys(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(set(result.keys()), {"success", "message_id", "attempts", "error"})

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_field_is_bool(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        result = send_alert(_VALID_PAYLOAD)
        self.assertIs(type(result["success"]), bool)
        self.assertTrue(result["success"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_attempts_field_is_int_on_success(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        result = send_alert(_VALID_PAYLOAD)
        self.assertIs(type(result["attempts"]), int)
        self.assertEqual(result["attempts"], 1)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {}, clear=True)
    def test_preflight_failure_has_four_keys_and_zero_attempts(self, mock_post):
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(set(result.keys()), {"success", "message_id", "attempts", "error"})
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_delivery_failure_has_four_keys_and_nonzero_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = [_api_resp(500), _api_resp(500), _api_resp(500)]
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(set(result.keys()), {"success", "message_id", "attempts", "error"})
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_permanent_failure_has_four_keys_and_one_attempt(self, mock_post):
        mock_post.return_value = _api_resp(401)
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(set(result.keys()), {"success", "message_id", "attempts", "error"})
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_connection_error_has_four_keys_and_three_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.ConnectionError("down")
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(set(result.keys()), {"success", "message_id", "attempts", "error"})
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])


class TestSuccessPath(unittest.TestCase):
    """Correct return values on HTTP 200 and on retry-then-succeed sequences."""

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_http_200_first_attempt_returns_success(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        result = send_alert(_VALID_PAYLOAD)
        self.assertTrue(result["success"])
        self.assertEqual(result["message_id"], 42)
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_500_twice_then_200_returns_success_with_three_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _api_resp(500),
            _api_resp(500),
            _api_resp(200, _SUCCESS_BODY),
        ]
        result = send_alert(_VALID_PAYLOAD)
        self.assertTrue(result["success"])
        self.assertEqual(result["message_id"], 42)
        self.assertEqual(result["attempts"], 3)
        self.assertIsNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_id_is_none_when_response_json_lacks_result_key(self, mock_post):
        mock_post.return_value = _api_resp(200, {"ok": True})
        result = send_alert(_VALID_PAYLOAD)
        self.assertTrue(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_does_not_raise_on_valid_input(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        try:
            result = send_alert(_VALID_PAYLOAD)
            self.assertTrue(result["success"])
            self.assertEqual(result["attempts"], 1)
        except Exception as exc:
            self.fail(f"send_alert raised {exc!r} on valid input")

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_false_after_exhausting_all_retries(self, mock_post, mock_sleep):
        mock_post.side_effect = [_api_resp(500), _api_resp(500), _api_resp(500)]
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_false_on_permanent_4xx_failure(self, mock_post):
        mock_post.return_value = _api_resp(401)
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 1)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_false_and_zero_attempts_on_missing_env_var(self, mock_post, mock_sleep):
        with patch.dict(os.environ, {}, clear=True):
            result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_success_false_and_zero_attempts_on_invalid_payload(self, mock_post):
        result = send_alert({"ticker": "AAPL"})
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()


class TestRetryExhaustion(unittest.TestCase):
    """All retry slots consumed before failure is returned; no exception escapes."""

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_500_three_times_returns_failure_with_three_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = [_api_resp(500), _api_resp(500), _api_resp(500)]
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsInstance(result["error"], str)
        self.assertGreater(len(result["error"]), 0)

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_connection_error_three_times_returns_failure_with_three_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.ConnectionError("network down")
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsInstance(result["error"], str)
        self.assertGreater(len(result["error"]), 0)

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_timeout_three_times_returns_failure_with_three_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.Timeout("timed out")
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 3)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_does_not_raise_on_connection_error(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.ConnectionError("network down")
        try:
            result = send_alert(_VALID_PAYLOAD)
            self.assertFalse(result["success"])
            self.assertIsNone(result["message_id"])
            self.assertEqual(result["attempts"], 3)
            self.assertIsNotNone(result["error"])
        except Exception as exc:
            self.fail(f"send_alert raised {exc!r} on connection error")


class TestPermanentFailure(unittest.TestCase):
    """4xx responses exit immediately with attempts=1; no retry loop is entered."""

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_http_401_does_not_retry_and_returns_one_attempt(self, mock_post):
        mock_post.return_value = _api_resp(401)
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(mock_post.call_count, 1)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_http_400_does_not_retry_and_returns_one_attempt(self, mock_post):
        mock_post.return_value = _api_resp(400)
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(mock_post.call_count, 1)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_http_403_does_not_retry_and_returns_one_attempt(self, mock_post):
        mock_post.return_value = _api_resp(403)
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(mock_post.call_count, 1)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_4xx_error_field_is_non_empty_string(self, mock_post):
        mock_post.return_value = _api_resp(401)
        result = send_alert(_VALID_PAYLOAD)
        self.assertIsInstance(result["error"], str)
        self.assertGreater(len(result["error"]), 0)
        self.assertIsNone(result["message_id"])


class TestPreflightFailures(unittest.TestCase):
    """Validation and config failures return attempts=0 and make no HTTP call."""

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_token_returns_failure_zero_attempts_no_http(self, mock_post):
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "-100123"})
    def test_blank_token_returns_failure_zero_attempts_no_http(self, mock_post):
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc123", "TELEGRAM_CHAT_ID": ""})
    def test_blank_chat_id_returns_failure_zero_attempts_no_http(self, mock_post):
        result = send_alert(_VALID_PAYLOAD)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_missing_ticker_returns_failure_zero_attempts_no_http(self, mock_post):
        payload = {"signal": "BUY", "severity": "LOW", "reason": "Strong earnings"}
        result = send_alert(payload)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_none_field_value_returns_failure_zero_attempts_no_http(self, mock_post):
        payload = {**_VALID_PAYLOAD, "signal": None}
        result = send_alert(payload)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_blank_string_field_returns_failure_zero_attempts_no_http(self, mock_post):
        payload = {**_VALID_PAYLOAD, "reason": "   "}
        result = send_alert(payload)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_payload_not_a_dict_returns_failure_zero_attempts_no_http(self, mock_post):
        result = send_alert("TSLA:SELL")
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_none_payload_returns_failure_zero_attempts_no_http(self, mock_post):
        result = send_alert(None)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNone(result["message_id"])
        self.assertIsNotNone(result["error"])
        mock_post.assert_not_called()

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_preflight_error_field_is_non_empty_string(self, mock_post):
        result = send_alert(None)
        self.assertIsInstance(result["error"], str)
        self.assertGreater(len(result["error"]), 0)
        self.assertEqual(result["attempts"], 0)


class TestMessageContent(unittest.TestCase):
    """POST body text contains all 4 payload fields; message is not sent when delivery is blocked."""

    def _get_post_text(self, mock_post):
        args, kwargs = mock_post.call_args
        return kwargs["json"]["text"]

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_contains_ticker(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        send_alert(_VALID_PAYLOAD)
        text = self._get_post_text(mock_post)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        self.assertIn("TSLA", text)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_contains_signal(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        send_alert(_VALID_PAYLOAD)
        text = self._get_post_text(mock_post)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        self.assertIn("SELL", text)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_contains_severity(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        send_alert(_VALID_PAYLOAD)
        text = self._get_post_text(mock_post)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        self.assertIn("HIGH", text)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_contains_reason(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        send_alert(_VALID_PAYLOAD)
        text = self._get_post_text(mock_post)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        self.assertIn("Earnings miss and reduced forward guidance", text)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_post_uses_correct_chat_id(self, mock_post):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        send_alert(_VALID_PAYLOAD)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], "-100123456789")
        self.assertIn("text", kwargs["json"])
        self.assertIsInstance(kwargs["json"]["text"], str)

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_no_post_when_payload_field_is_missing(self, mock_post):
        result = send_alert({"ticker": "AAPL", "signal": "BUY", "severity": "LOW"})
        mock_post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {}, clear=True)
    def test_no_post_when_env_vars_are_missing(self, mock_post):
        result = send_alert(_VALID_PAYLOAD)
        mock_post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_no_post_when_payload_is_not_a_dict(self, mock_post):
        result = send_alert(42)
        mock_post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 0)
        self.assertIsNotNone(result["error"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_message_text_is_consistent_across_retry_attempts(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _api_resp(500),
            _api_resp(200, _SUCCESS_BODY),
        ]
        send_alert(_VALID_PAYLOAD)
        self.assertEqual(mock_post.call_count, 2)
        first_text = mock_post.call_args_list[0][1]["json"]["text"]
        second_text = mock_post.call_args_list[1][1]["json"]["text"]
        self.assertEqual(first_text, second_text)
        self.assertIn("TSLA", first_text)
        self.assertIsInstance(first_text, str)


class TestBackoffTiming(unittest.TestCase):
    """sleep() is called with exact intervals and only between non-final attempts."""

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_two_failures_produce_sleep_intervals_1_and_2(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _api_resp(500),
            _api_resp(500),
            _api_resp(200, _SUCCESS_BODY),
        ]
        send_alert(_VALID_PAYLOAD)
        self.assertEqual(mock_sleep.call_args_list, [call(1), call(2)])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_three_failures_produce_exactly_two_sleeps(self, mock_post, mock_sleep):
        mock_post.side_effect = [_api_resp(500), _api_resp(500), _api_resp(500)]
        send_alert(_VALID_PAYLOAD)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(mock_sleep.call_args_list, [call(1), call(2)])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_no_sleep_on_first_attempt_success(self, mock_post, mock_sleep):
        mock_post.return_value = _api_resp(200, _SUCCESS_BODY)
        result = send_alert(_VALID_PAYLOAD)
        mock_sleep.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 1)

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_no_sleep_on_4xx_permanent_failure(self, mock_post, mock_sleep):
        mock_post.return_value = _api_resp(401)
        result = send_alert(_VALID_PAYLOAD)
        mock_sleep.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 1)

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, {}, clear=True)
    def test_no_sleep_on_preflight_failure(self, mock_post, mock_sleep):
        result = send_alert(_VALID_PAYLOAD)
        mock_sleep.assert_not_called()
        mock_post.assert_not_called()
        self.assertEqual(result["attempts"], 0)
        self.assertFalse(result["success"])

    @patch("data.notifier.time.sleep")
    @patch("data.notifier.requests.post")
    @patch.dict(os.environ, _VALID_ENV)
    def test_single_failure_then_success_produces_one_sleep_of_1s(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _api_resp(500),
            _api_resp(200, _SUCCESS_BODY),
        ]
        result = send_alert(_VALID_PAYLOAD)
        self.assertEqual(mock_sleep.call_args_list, [call(1)])
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
