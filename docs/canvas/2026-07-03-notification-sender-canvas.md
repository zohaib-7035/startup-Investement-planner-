# REASONS Canvas: Notification Sender
Date: 2026-07-03
Analysis: 2026-07-03-notification-sender-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The pipeline has no way to emit trade signals to external consumers. Alert payloads produced by upstream modules (screener, risk) sit unused — there is no delivery channel to notify a human operator or downstream system when a high-severity signal fires.

**Goal:** `data/notifier.py` exposes a single `send_alert(alert_payload)` function that takes a structured dict, formats it into a human-readable message, and delivers it to a Telegram chat via the Bot API — with automatic retry on transient failures and a safe fallback return on all error conditions.

**Definition of Done:**
- [ ] Given a valid payload and both env vars set, when the Telegram API responds 200, then `send_alert` returns `{success: True, message_id: <int>, attempts: 1, error: None}`
- [ ] Given the API returns 500 on attempts 1 and 2 then 200 on attempt 3, when `send_alert` is called, then it returns `{success: True, message_id: <int>, attempts: 3, error: None}`
- [ ] Given the API returns 500 on all 3 attempts, when `send_alert` is called, then it returns `{success: False, message_id: None, attempts: 3, error: <non-empty string>}`
- [ ] Given a `requests.ConnectionError` on every attempt, when `send_alert` is called, then it returns `{success: False, message_id: None, attempts: 3, error: <non-empty string>}`
- [ ] Given `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing or blank, when `send_alert` is called, then it returns `{success: False, message_id: None, attempts: 0, error: <non-empty string>}` and makes no HTTP request
- [ ] Given a payload with a missing or None field, when `send_alert` is called, then it returns `{success: False, message_id: None, attempts: 0, error: <non-empty string>}` and makes no HTTP request
- [ ] Given a valid payload, when the message is formatted, then the Telegram message text contains the ticker, signal, severity, and reason values
- [ ] Given a HTTP 401 response, when `send_alert` is called, then it does NOT retry and returns `{success: False, message_id: None, attempts: 1, error: <non-empty string>}`
- [ ] `data/notifier.py` exists; `tests/test_notifier.py` all pass; no regression in 174 existing tests
- [ ] `.env.example` updated with `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` entries

---

## E — Entities

### Module Constructs

| Construct | Type | Fields / Signature | Notes |
|-----------|------|-------------------|-------|
| `_EMPTY_RESULT` | Module-level constant | `{success: False, message_id: None, attempts: 0, error: None}` | Pre-flight failure fallback; `attempts: 0` signals no HTTP call was made |
| `_REQUIRED_PAYLOAD_KEYS` | Module-level constant | `("ticker", "signal", "severity", "reason")` | Used by `_validate_payload`; single source of truth for required fields |
| `_validate_payload` | Private helper | `(alert_payload) → None or str` | Returns `None` on success; returns error string on any structural or type failure |
| `_get_telegram_config` | Private helper | `() → (token: str, chat_id: str)` | Reads env vars; raises `ValueError` if either is missing or blank |
| `_format_message` | Private helper | `(alert_payload: dict) → str` | Builds Telegram message string; all 4 payload fields must appear in output |
| `_post_with_retry` | Private helper | `(url, payload, max_attempts, backoff_base) → (response or None, attempts: int, error: str or None)` | HTTP POST loop with backoff; no retry on 4xx; `time.sleep(backoff_base ** attempt)` between transient failures |
| `send_alert` | Public function | `(alert_payload: dict) → dict` | Thin orchestrator: validate → config → format → deliver → return; outer `try/except Exception` wraps everything |

---

## A — Approach

**Pattern:** Module-per-concern thin orchestrator with dedicated retry helper

**Strategy:** `send_alert` owns the end-to-end delivery contract but delegates each concern to a focused private helper — validation, config reading, message formatting, and HTTP delivery are all separate. `_post_with_retry` is the only function that calls `requests.post` or `time.sleep`, which makes both patchable at the module level in tests without any leakage between test classes. This mirrors the `edgar_client.py` pattern exactly: a public function that composes private helpers, each individually testable in isolation. The outer `try/except Exception` on `send_alert` is the universal safety net that ensures the module never raises to the caller regardless of what fails internally.

**Scope In:**
- Telegram Bot API delivery only
- 3-attempt exponential backoff (1s → 2s → 4s) on 5xx and connection/timeout errors
- Pre-flight validation of payload structure and env var presence
- `attempts: 0` for pre-flight failures; `attempts: 1–3` for delivery failures
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `os.environ` only

**Scope Out:**
- No other notification channels (email, Slack, SMS)
- No notification queuing, scheduling, or batching
- No sent notification history persisted to any store
- No user subscription routing
- No retry-after handling for HTTP 429 (known limitation, future story)
- No runtime-configurable message templates

---

## S — Structure

**Module path:** `Z:\claude\stock_analyzer\data\`

**New Files:**
- `data/notifier.py` — full implementation of `send_alert`, all private helpers, module-level constants

**Modified Files:**
- `.env.example` — add `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` entries with explanatory comments

**New Test File:**
- `tests/test_notifier.py` — all scenarios mocked; patches `data.notifier.requests.post` and `data.notifier.time.sleep`

**No database, no migrations, no ORM** — pure Python HTTP delivery module

---

## O — Operations

1. Create `data/notifier.py` — define `_EMPTY_RESULT` dict constant with keys `success=False, message_id=None, attempts=0, error=None`; define `_REQUIRED_PAYLOAD_KEYS` tuple containing `"ticker"`, `"signal"`, `"severity"`, `"reason"`; add `import os`, `import time`, `import requests` at module top

2. Implement `_validate_payload(alert_payload)` in `data/notifier.py` — check `isinstance(alert_payload, dict)` first; then verify all four keys in `_REQUIRED_PAYLOAD_KEYS` are present; then verify each value is a non-empty string (not None, not blank); return `None` on success, return a descriptive error string on the first failure found

3. Implement `_get_telegram_config()` in `data/notifier.py` — read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `os.environ`; treat blank strings as missing; raise `ValueError` with a descriptive message if either is absent or blank; return `(token, chat_id)` as a 2-tuple of strings on success

4. Implement `_format_message(alert_payload)` in `data/notifier.py` — build a plain-text string that contains all four values: ticker, signal, severity, and reason; the exact format is flexible but all four values must appear as readable fields

5. Implement `_post_with_retry(url, payload, max_attempts, backoff_base)` in `data/notifier.py` — loop from attempt 1 through `max_attempts`; call `requests.post(url, json=payload, timeout=10)` on each attempt; if the response status code is in the 4xx range, exit the loop immediately and return `(response, attempt_count, error_string)`; if the response status code is in the 5xx range or a `requests.exceptions.RequestException` is raised, call `time.sleep(backoff_base ** attempt)` before the next attempt (do not sleep after the final attempt); after exhausting all attempts without success, return `(None, max_attempts, error_string)`; on 2xx success, return `(response, attempt_count, None)`

6. Implement `send_alert(alert_payload)` in `data/notifier.py` — wrap the entire body in `try/except Exception: return _EMPTY_RESULT.copy()`; call `_validate_payload` first and return `_EMPTY_RESULT.copy()` with the error string if it fails; call `_get_telegram_config` and return `_EMPTY_RESULT.copy()` with the error string if it raises; call `_format_message`; build the Telegram API URL as `https://api.telegram.org/bot{token}/sendMessage`; build the POST payload dict with `chat_id` and `text` keys; call `_post_with_retry(url, post_payload, max_attempts=3, backoff_base=2)`; on success, extract `message_id` from `response.json()["result"]["message_id"]` wrapped in its own try/except; return the final result dict with correct `success`, `message_id`, `attempts`, and `error` values

7. Update `.env.example` — append `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` with a comment explaining that `TELEGRAM_BOT_TOKEN` is the raw token without the "bot" prefix (e.g. `123456:ABCxyz`, not `bot123456:ABCxyz`)

8. Create `tests/test_notifier.py` — define a module-level `_api_resp(status_code, body)` helper that builds a `MagicMock` with `.status_code` and `.json.return_value` set; write test classes: `TestSendAlertSchema` (result has exactly 4 keys, correct types), `TestSuccessPath` (HTTP 200 first attempt; retry 500×2 then 200 on attempt 3), `TestRetryExhaustion` (500×3; ConnectionError×3; Timeout×3), `TestPermanentFailure` (HTTP 401 no retry; HTTP 400 no retry), `TestPreflightFailures` (missing env var, blank env var, missing payload key, None payload value, payload not a dict), `TestMessageContent` (all 4 fields appear in the POST body text), `TestBackoffTiming` (assert `mock_sleep.call_args_list` contains the correct 1s and 2s sleep calls for a 2-fail-then-succeed sequence); all HTTP calls patched with `@patch("data.notifier.requests.post")`; all sleep calls patched with `@patch("data.notifier.time.sleep")`; env vars controlled with `@patch.dict(os.environ, {...})` or `@patch.dict(os.environ, {}, clear=True)`

---

## N — Norms

### Pipeline Norms (Python)

- Module-per-concern: each `data/` module owns exactly one concern; `notifier.py` owns HTTP delivery only
- Module-level constant for the fallback return value; always return `.copy()` — never return the constant directly
- Every public function has an outer `try/except Exception` as the last safety net — never raises to the caller
- Return dicts use Python-native types only — no numpy scalars, no pandas objects
- Private helpers are prefixed with `_`; public functions have no underscore prefix
- Env vars read via `os.environ` — never hardcode tokens, chat IDs, or secrets anywhere in the module
- HTTP calls use `requests` with an explicit `timeout` argument on every call
- All HTTP calls are patchable via `@patch("data.notifier.requests.<method>")` — no global state, no singletons
- `time.sleep` is the only mechanism for backoff delay — it is patched in tests at `data.notifier.time.sleep`
- No logging or print statements — the return dict is the only communication channel

---

## S — Safeguards

### Pipeline Safeguards

- Never hardcode `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, or any secret in source files
- Never raise to the caller — the outer `try/except Exception` is mandatory on `send_alert`
- Do not mutate `_EMPTY_RESULT` — always return `.copy()`
- The `time.sleep` call must be placed inside `_post_with_retry` and must NOT be called after the final attempt (to avoid a gratuitous sleep when no retry follows)
- `_post_with_retry` must treat ALL 4xx codes as permanent failures — no special-casing of individual codes other than the range check
- Tests must never make real HTTP calls — `@patch("data.notifier.requests.post")` is required on every test method that exercises any HTTP path
- Tests must never call real `time.sleep` — `@patch("data.notifier.time.sleep")` is required on every test that exercises a retry path
- `TELEGRAM_BOT_TOKEN` env var comment in `.env.example` must warn against including the "bot" prefix
- HTTP 429 is intentionally not retried under the 4xx rule — document this as a known limitation in the module

---

## Change Log

*(appended by /prompt-update and /sync)*
