import os
import time

import requests

_EMPTY_RESULT = {
    "success": False,
    "message_id": None,
    "attempts": 0,
    "error": None,
}

_REQUIRED_PAYLOAD_KEYS = ("ticker", "signal", "severity", "reason")

# HTTP 429 (rate limit) falls under 4xx and is not retried under the permanent-failure rule.
# Future story: add retry-after handling for 429 specifically.


def _validate_payload(alert_payload):
    if not isinstance(alert_payload, dict):
        return "alert_payload must be a dict"
    for key in _REQUIRED_PAYLOAD_KEYS:
        if key not in alert_payload:
            return f"Missing required field: '{key}'"
        value = alert_payload[key]
        if not isinstance(value, str) or not value.strip():
            return f"Field '{key}' must be a non-empty string"
    return None


def _get_telegram_config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN env var is missing or blank")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID env var is missing or blank")
    return token, chat_id


def _format_message(alert_payload):
    reason = (alert_payload.get("reason") or "").strip() or "â€”"
    return (
        f"Stock Alert\n"
        f"Ticker:   {alert_payload['ticker']}\n"
        f"Signal:   {alert_payload['signal']}\n"
        f"Severity: {alert_payload['severity']}\n"
        f"Reason:   {reason}"
    )


def _post_with_retry(url, payload, max_attempts, backoff_base):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code // 100 == 2:
                return response, attempt, None
            if response.status_code // 100 == 4:
                return response, attempt, f"Permanent failure: HTTP {response.status_code}"
            last_error = f"HTTP {response.status_code} on attempt {attempt}"
        except requests.exceptions.RequestException as exc:
            last_error = str(exc) or f"Connection error on attempt {attempt}"
        if attempt < max_attempts:
            time.sleep(backoff_base ** (attempt - 1))
    return None, max_attempts, last_error or f"All {max_attempts} attempts failed"


def send_alert(alert_payload) -> dict:
    try:
        validation_error = _validate_payload(alert_payload)
        if validation_error is not None:
            result = _EMPTY_RESULT.copy()
            result["error"] = validation_error
            return result

        try:
            token, chat_id = _get_telegram_config()
        except ValueError as exc:
            result = _EMPTY_RESULT.copy()
            result["error"] = str(exc)
            return result

        text = _format_message(alert_payload)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        post_payload = {"chat_id": chat_id, "text": text}

        response, attempts, error = _post_with_retry(
            url, post_payload, max_attempts=3, backoff_base=2
        )

        if error is not None:
            return {
                "success": False,
                "message_id": None,
                "attempts": attempts,
                "error": error,
            }

        message_id = None
        try:
            message_id = response.json()["result"]["message_id"]
        except Exception:
            pass

        return {
            "success": True,
            "message_id": message_id,
            "attempts": attempts,
            "error": None,
        }
    except Exception:
        return _EMPTY_RESULT.copy()
