# User Story: Notification Sender

Date: 2026-07-03
Source: Pasted text

---

## Story 16: Send Financial Alert via Telegram

**As a** system orchestrating the stock intelligence pipeline,
**I want** to send a structured financial alert dict (ticker, signal, severity, reason) to a Telegram chat via the Bot API — with automatic retries and production-grade error handling,
**So that** downstream consumers receive timely, reliable trade signals without the caller needing to handle delivery failures.

### Scope In
- New module `data/notifier.py` exposing one public function `send_alert(alert_payload)`
- `alert_payload` accepts a dict with keys `ticker (str)`, `signal (str)`, `severity (str)`, `reason (str)`
- Formats the payload into a human-readable Telegram message (Markdown or plain text)
- Delivers via HTTP POST to `https://api.telegram.org/bot{TOKEN}/sendMessage` using `requests` (already in `requirements.txt`)
- Bot token read from `TELEGRAM_BOT_TOKEN` env var; target chat ID from `TELEGRAM_CHAT_ID` env var
- Retry logic: up to 3 attempts with exponential backoff (1 s → 2 s → 4 s) on transient failures (connection error, timeout, HTTP 5xx)
- No retry on permanent failures (HTTP 4xx — bad token, bad chat ID)
- Returns `{success (bool), message_id (int|None), attempts (int), error (str|None)}`
- Module-level `_EMPTY_RESULT` constant; outer `try/except` on public function; never raises
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` missing or blank → return failure result immediately, no HTTP call made

### Scope Out
- Multiple notification channels (email, Slack, SMS) — Telegram only in this story
- Notification queuing, scheduling, or batching
- Storing sent notification history to a database or file
- User subscription management or routing logic
- Formatting templates configurable at runtime

### Acceptance Criteria

- **Given** a valid alert payload and both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, **when** `send_alert` is called and the Telegram API responds with HTTP 200, **then** the function returns `{success: True, message_id: <int>, attempts: 1, error: None}`.

- **Given** the Telegram API returns HTTP 500 on the first two attempts then HTTP 200 on the third, **when** `send_alert` is called, **then** it retries automatically, returns `{success: True, message_id: <int>, attempts: 3, error: None}`, and does not raise.

- **Given** the Telegram API returns HTTP 500 on all 3 attempts, **when** `send_alert` is called, **then** it returns `{success: False, message_id: None, attempts: 3, error: <non-empty string>}` and does not raise.

- **Given** a connection error (e.g. `requests.ConnectionError`) on every attempt, **when** `send_alert` is called, **then** it exhausts all retries, returns `{success: False, message_id: None, attempts: 3, error: <non-empty string>}`, and does not raise.

- **Given** `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing or blank, **when** `send_alert` is called, **then** it returns `{success: False, message_id: None, attempts: 0, error: <non-empty string>}` immediately without making any HTTP request.

- **Given** an alert payload with missing or None fields (e.g. `ticker` is absent), **when** `send_alert` is called, **then** it returns `{success: False, message_id: None, attempts: 0, error: <non-empty string>}` without making any HTTP request.

- **Given** a valid alert payload, **when** the message is formatted, **then** the Telegram message text contains the `ticker`, `signal`, `severity`, and `reason` values from the payload.

- **Given** a HTTP 401 response (invalid token), **when** `send_alert` is called, **then** it does NOT retry (4xx is permanent), returns `{success: False, message_id: None, attempts: 1, error: <non-empty string>}`.

### Definition of Done
- [ ] `data/notifier.py` implemented with `send_alert()`, `_EMPTY_RESULT`, and retry logic
- [ ] `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` read from `os.environ` — never hardcoded
- [ ] `tests/test_notifier.py` written; all tests pass (all mocked — no real HTTP calls)
- [ ] `/test-review` run — Recommendation: Ready
- [ ] No regression in existing 174 tests
- [ ] `.env.example` updated with `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_CHAT_ID=` entries
