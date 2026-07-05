# Analysis: Notification Sender

Date: 2026-07-03
Story: docs/story/2026-07-03-notification-sender-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline with 14 modules under `data/`. No web framework, no ORM, no persistence. `requests==2.32.4` is already installed and used by `data/edgar_client.py` for multi-step HTTP flows — the closest pattern model for this story. `os.environ` for secret injection is already established in `edgar_client.py` (`SEC_USER_AGENT`) and implied by `ANTHROPIC_API_KEY` in `.env.example`. No existing retry logic anywhere in the codebase — this story introduces that pattern for the first time.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_EMPTY_FILING` module-level constant | `data/edgar_client.py:7` | All-None fallback returned via `.copy()` — structural model for `_EMPTY_RESULT` |
| `_get_headers()` private helper | `data/edgar_client.py:16` | Reads `os.environ.get(...)` and returns config dict — same pattern as `_get_telegram_config()` |
| `requests.get()` with `raise_for_status()` and `timeout` | `data/edgar_client.py:33` | Established `requests` usage pattern; `notifier.py` uses `requests.post()` instead |
| `@patch("data.edgar_client.requests.get")` mock pattern | `tests/test_edgar_client.py:59` | Direct model for `@patch("data.notifier.requests.post")` |
| `mock.side_effect = [resp1, resp2, resp3]` sequencing | `tests/test_edgar_client.py:50` | Already used for multi-call HTTP mocking — ideal for retry sequences (500→500→200) |
| `_json_resp()` / `_text_resp()` mock helper functions | `tests/test_edgar_client.py:36` | Response builder pattern; `test_notifier.py` needs an equivalent `_api_resp(status_code, body)` |
| `ANTHROPIC_API_KEY`, `SEC_USER_AGENT`, `CHROMA_PERSIST_DIR` | `.env.example` | Established pattern for env-var documentation; two new vars must be added |
| Outer `try/except Exception → fallback.copy()` | All `data/` modules | Universal error boundary; `send_alert` must follow the same contract |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/notifier.py` | New Python module | Does not exist; entry point for all Telegram alerting logic |
| `send_alert(alert_payload)` | Public function | Validates payload, reads config, formats message, calls Telegram, handles retries |
| `_EMPTY_RESULT` | Module-level dict constant | `{success: False, message_id: None, attempts: 0, error: None}` — pre-flight fallback; attempts=0 distinguishes from delivery failures |
| `_REQUIRED_PAYLOAD_KEYS` | Module-level constant | Tuple of required string keys: `("ticker", "signal", "severity", "reason")` |
| `_validate_payload(alert_payload)` | Private helper | Returns None on success, error string on failure; checks dict type, required keys, non-empty string values |
| `_get_telegram_config()` | Private helper | Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `os.environ`; raises ValueError if either is missing or blank |
| `_format_message(alert_payload)` | Private helper | Builds Telegram message string containing all 4 payload field values |
| `_post_with_retry(url, payload, max_attempts, backoff_base)` | Private helper | HTTP POST loop; retries on 5xx and connection/timeout errors; does NOT retry on 4xx; returns (response_or_None, attempts, error_str_or_None) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars | `.env.example` entries | Must be added with placeholder values and comments |
| `tests/test_notifier.py` | New test file | All HTTP mocked via `@patch("data.notifier.requests.post")`; `time.sleep` mocked via `@patch("data.notifier.time.sleep")` |

---

## Strategic Approach

`data/notifier.py` follows the module-per-concern pattern established in `edgar_client.py` — it owns the HTTP delivery concern and nothing else. A dedicated `_post_with_retry` private helper encapsulates the loop, attempt counter, and backoff logic, keeping `send_alert` a thin orchestrator: validate → read config → format message → deliver → return. The `time.sleep` call for backoff lives inside `_post_with_retry`, so tests patch `data.notifier.time.sleep` to eliminate real wait times — the same module-scoped patch technique already proven in `test_edgar_client.py`. The `side_effect` list technique maps perfectly onto retry sequences: `[mock_500, mock_500, mock_200]` for a 2-fail-then-succeed scenario.

---

## Key Design Decisions

- `_EMPTY_RESULT` has `attempts: 0` — distinguishes pre-flight validation failures (no HTTP call made) from delivery failures (1–3 attempts recorded). The function builds its own result dict for delivery outcomes rather than mutating `_EMPTY_RESULT`.
- `time.sleep` is called inside `_post_with_retry` and patched in tests via `@patch("data.notifier.time.sleep")` — no real delays in the test suite; tests also assert `mock_sleep.call_args_list` to verify backoff intervals were correct.
- 4xx responses are permanent failures — no retry. `response.status_code // 100 == 4` is the guard; the loop exits immediately and returns `attempts=1`.
- 5xx and `requests.exceptions.RequestException` subclasses are transient — both trigger retry up to `max_attempts`.
- `message_id` is read from `response.json()["result"]["message_id"]` — standard Telegram API shape on success.
- `requests.post` timeout set to 10 seconds per attempt — follows `edgar_client.py` precedent.
- `TELEGRAM_BOT_TOKEN` env var stores the raw token WITHOUT the "bot" prefix — the module constructs the URL as `https://api.telegram.org/bot{token}/sendMessage` internally.
- HTTP 429 (rate limit) falls under 4xx and will NOT be retried — known limitation; a future story can add retry-after handling.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Real `time.sleep` calls making tests slow | High | Must patch `data.notifier.time.sleep` in all retry tests; unpatched 3-retry test waits 7 real seconds |
| `response.json()` failing on non-JSON 200 response | Medium | Outer try/except covers it; message_id falls back to None; success still True if HTTP status was 200 |
| HTTP 429 (rate limiting) not retried under 4xx rule | Medium | Documented known limitation; treat as out-of-scope for this story |
| `alert_payload` is not a dict (e.g. caller passes a string) | Low | `_validate_payload` must check `isinstance(alert_payload, dict)` before key access |
| `TELEGRAM_BOT_TOKEN` env var includes "bot" prefix from user misconfiguration | Low | Document in `.env.example` comment: store raw token only, not "bot123:ABC" |
| Backoff interval precision | Low | Sequence is 1s→2s→4s (`backoff_base ** attempt` where attempt is 1-indexed); tests assert exact call_args_list |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| HTTP 200 on first attempt → success=True, attempts=1, error=None | Needs work | `mock_post.return_value` with status_code=200 and Telegram JSON body |
| HTTP 500 × 2 then HTTP 200 → success=True, attempts=3 | Needs work | `side_effect=[mock_500, mock_500, mock_200]` — identical to edgar_client multi-call pattern |
| HTTP 500 × 3 → success=False, attempts=3, non-empty error | Needs work | `side_effect=[mock_500, mock_500, mock_500]` |
| ConnectionError × 3 → success=False, attempts=3, non-empty error | Needs work | `side_effect=requests.ConnectionError` raised on each call |
| Missing/blank env var → success=False, attempts=0, no HTTP call | Needs work | `@patch.dict(os.environ, {}, clear=True)` to strip env vars |
| Missing payload field → success=False, attempts=0, no HTTP call | Needs work | `_validate_payload` guard fires before any HTTP call |
| Message text contains all 4 payload field values | Needs work | Capture the `text` param in the `requests.post` call and assert all values present |
| HTTP 401 → success=False, attempts=1, no retry | Needs work | 4xx guard exits loop; verify `mock_post.call_count == 1` |

---

## Dependencies

- `requests` — already in `requirements.txt` (used by `edgar_client.py`); no new package required
- `time` — stdlib; `time.sleep` for exponential backoff
- `os` — stdlib; `os.environ` for token and chat ID
- `.env.example` — must be updated with two new env var entries
- No other `data/` module imported — `notifier.py` is self-contained
