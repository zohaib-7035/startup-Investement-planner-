# Analysis: Get Stock History via yfinance
Date: 2026-06-30
Story: 2026-06-30-get-stock-history-yfinance-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local — greenfield, no Python source files found)

---

## Project Fingerprint

This is a greenfield Python project for financial data retrieval and analysis. The repository currently contains only a PDF blueprint (`AI Stock Intelligence Platform (Production Blueprint).pdf`) and the generated story file — no source code exists yet. The intended runtime environment has Python with `yfinance` installed. No framework, ORM, or module structure is in place; the entire data layer needs to be established from scratch.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `yfinance` library | Runtime environment (installed) | External dependency — provides `Ticker.history()` as the primary data retrieval surface |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `get_stock_history` function | Python function | Core deliverable of this story — does not exist yet |
| Stock data module / file | Python module (e.g. `data/stock.py`) | No source file exists; module layout TBD from blueprint |
| OHLCV schema normaliser | Logic inside `get_stock_history` | Maps yfinance DataFrame columns → `date`, `open`, `high`, `low`, `close`, `volume` dicts |
| Invalid ticker guard | Error-handling logic | Catches yfinance silent failures (empty DataFrame or metadata-only response) and either returns `[]` or raises `ValueError` |
| Date input normaliser | Logic inside function | Accepts both `str` and `datetime.date`/`datetime.datetime` and converts to yfinance-compatible string format |
| Unit test suite | `tests/test_stock.py` (or similar) | Must cover happy path, empty range, weekend-only range, invalid ticker, future date range |

---

## Strategic Approach

Build `get_stock_history` as a thin, stateless wrapper around `yfinance.Ticker.history()`. The function's responsibility ends at normalising the yfinance DataFrame into the agreed OHLCV dict schema — no caching, no persistence, no enrichment. Keep it in a dedicated module (e.g. `data/stock.py`) so downstream consumers (analytics, charting, model training) import a stable interface that can later be swapped for a different data provider without touching call sites. The invalid-ticker guard is the most critical non-obvious piece: yfinance returns an empty DataFrame for unknown tickers rather than raising, so the function must detect and handle that explicitly.

---

## Key Design Decisions

- **Use `Ticker.history()` over the legacy `download()` call** — `history()` returns a properly indexed DataFrame per ticker and is the recommended yfinance API for single-symbol queries.
- **Normalise the index before building dicts** — yfinance returns a DatetimeIndex (timezone-aware); strip timezone and format as `YYYY-MM-DD` string to satisfy the ISO 8601 requirement.
- **Do not rely on yfinance ordering alone** — verify ascending order from yfinance, but add an explicit `sorted()` guard to make the contract unconditional across yfinance versions.
- **Return `[]` rather than raising for empty ranges and future dates** — consistent with story AC; raise `ValueError` only for provably invalid ticker symbols.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| yfinance returns empty DataFrame for invalid tickers silently (no exception) | High | Must explicitly check `df.empty` and guard accordingly — cannot rely on try/except alone |
| Timezone-aware DatetimeIndex causes date formatting inconsistencies | Medium | Strip tz with `.tz_localize(None)` or `.tz_convert(None)` before calling `.strftime()` |
| Market holidays within range produce gaps in dates | Medium | Expected behaviour — list simply omits non-trading days; document this clearly |
| yfinance `history()` end date is exclusive | Medium | yfinance treats `end` as exclusive; if caller passes `end_date = "2024-01-31"`, last record will be 2024-01-30. Must decide whether to add 1 day internally or document boundary |
| yfinance rate-limiting or network failure | Medium | No retry logic is in scope; let the exception propagate naturally — document as known limitation |
| Column name casing changes across yfinance versions | Low | yfinance has historically changed column names. Pin a version in `requirements.txt` and normalise with `.lower()` on column access |
| `volume` field returns float (not int) for some tickers | Low | Cast to `int` before returning to maintain schema consistency |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Valid symbol + date range → list with correct keys `date`, `open`, `high`, `low`, `close`, `volume` | Needs work | No implementation exists; straightforward to build with `Ticker.history()` + DataFrame normalisation |
| Returned list is in strict ascending date order | Needs work | yfinance returns ascending by default; add explicit sort guard for safety |
| `start_date == end_date` on a trading day → exactly one record | Needs work | Requires careful handling of yfinance's exclusive `end` parameter (add 1 day internally) |
| `start_date == end_date` on weekend/holiday → empty list, no error | Needs work | Handled naturally if `df.empty` check is in place |
| Invalid ticker → empty list or `ValueError`, no raw yfinance exception | Blocked | yfinance does not raise for unknown tickers — requires explicit `df.empty` check and deliberate error contract decision |
| Future date range → empty list | Needs work | yfinance returns empty DataFrame for future dates; covered by `df.empty` guard |

---

## Dependencies

- **`yfinance`** — primary external data source; version should be pinned in `requirements.txt`
- **`pandas`** — transitive dependency of yfinance; used internally to process the returned DataFrame
- **Downstream consumers (future)** — analytics module, charting module, model-training pipeline (all out of scope for this story; `get_stock_history` is their input boundary)
