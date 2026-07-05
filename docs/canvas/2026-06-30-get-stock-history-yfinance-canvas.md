# REASONS Canvas: Get Stock History via yfinance
Date: 2026-06-30
Analysis: 2026-06-30-get-stock-history-yfinance-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** No data retrieval layer exists. Downstream components (analytics, charting, model training) have no consistent, structured source for daily historical stock price data.

**Goal:** Implement a single public function `get_stock_history(symbol, start_date, end_date)` that fetches daily OHLCV data from yfinance and returns it as a list of dicts with a guaranteed schema, sorted ascending by date.

**Definition of Done:**
- [ ] Given a valid symbol and a date range containing trading days, when `get_stock_history` is called, then the function returns a non-empty list where every item has exactly the keys `date`, `open`, `high`, `low`, `close`, `volume`
- [ ] Given the returned list, when items are iterated, then dates are in strict ascending order with no duplicates
- [ ] Given `start_date == end_date` on a valid trading day, when called, then the list contains exactly one record
- [ ] Given `start_date == end_date` on a weekend or market holiday, when called, then the list is empty and no exception is raised
- [ ] Given an invalid or unknown ticker symbol, when called, then the function returns an empty list — a raw yfinance exception must never propagate to the caller
- [ ] Given a date range entirely in the future, when called, then the function returns an empty list
- [ ] Unit tests written and passing for: happy path, empty range, weekend-only range, invalid ticker, future date range
- [ ] Return schema validated (correct keys, ascending sort) in tests
- [ ] yfinance version pinned in `requirements.txt`

---

## E — Entities

### Data Entities

| Entity | Type | Key Fields | Relationships |
|--------|------|-----------|---------------|
| `OHLCVRecord` | Return schema (dict) | `date` (ISO 8601 str), `open` (float), `high` (float), `low` (float), `close` (float), `volume` (int) | Produced by `get_stock_history`; consumed by analytics, charting, model-training modules |
| `yfinance.Ticker` | External library object | Wraps a stock symbol; exposes `history()` | Input to the retrieval logic; not stored or passed outside the function |

No database schema or migration is involved — this is a stateless data retrieval function with no persistence layer.

---

## A — Approach

**Pattern:** Thin stateless wrapper over an external library, with explicit schema normalisation and contract-enforced error handling.

**Strategy:** Call `yfinance.Ticker(symbol).history(start=..., end=...)` to retrieve a pandas DataFrame, then normalise the result into the agreed OHLCV dict schema. The function owns the contract boundary: it strips timezone info from the DatetimeIndex, formats dates as ISO 8601 strings, casts volume to int, and adds an explicit ascending sort guard. Invalid tickers and empty ranges are handled at the `df.empty` check — no raw yfinance or pandas exceptions reach the caller. The function is placed in a dedicated module (`data/stock.py`) so callers import a stable interface that can be swapped for a different provider without touching call sites.

**Scope In:**
- Single-symbol daily OHLCV data retrieval via yfinance
- Input normalisation for both string and date-typed `start_date` / `end_date`
- Output schema: exactly `date`, `open`, `high`, `low`, `close`, `volume` — no extra fields
- Ascending date sort as a contractual guarantee
- Empty-list return for empty ranges, future dates, non-trading days, and invalid tickers
- Unit test coverage for all AC scenarios

**Scope Out:**
- Intraday (sub-daily) data resolution
- Adjusted close, dividend, or split fields
- Caching or persistence of fetched data
- Batch or multi-symbol fetching
- Retry logic for network failures
- Any frontend or API layer

---

## S — Structure

**Module:** `data/stock.py`

**New Files:**
- `data/__init__.py` — marks `data` as a Python package (empty)
- `data/stock.py` — contains `get_stock_history`; sole public interface for stock data retrieval
- `tests/__init__.py` — marks `tests` as a Python package (empty)
- `tests/test_stock.py` — unit tests covering all AC scenarios
- `requirements.txt` — pins `yfinance` and `pandas` at tested versions; includes `pytest`

**Modified Files:**
- None (greenfield project — no existing files to modify)

**Database:**
- None — no persistence layer in this story

---

## O — Operations

1. Create `requirements.txt` — pin `yfinance` at its current stable version and `pandas` as an explicit dependency; add `pytest` for the test suite
2. Create `data/__init__.py` — empty file to establish the `data` package
3. Create `data/stock.py` — implement `get_stock_history(symbol, start_date, end_date)`: normalise date inputs to strings, call `Ticker.history()` with end-date corrected by one day (yfinance end is exclusive), check `df.empty` and return empty list if true, strip timezone from the DatetimeIndex, iterate rows to build dicts with `date` (ISO 8601 string), `open`, `high`, `low`, `close` (floats), `volume` (int cast), sort list ascending by `date`, and return
4. Create `tests/__init__.py` — empty file to establish the `tests` package
5. Create `tests/test_stock.py` — unit tests: happy path; future date range; single-day on a trading day; single-day on a Saturday; invalid ticker symbol; assert schema keys exactly match; assert ascending date order — all yfinance calls mocked

---

## N — Norms

### Python / Data Pipeline Norms

- Module layout: `data/` for retrieval and transformation logic; `tests/` for all test files
- Functions are stateless — no side effects, no module-level mutable state
- All external library exceptions are caught at the function boundary — raw third-party exceptions do not propagate to callers
- Date inputs accept both `str` and `datetime.date` / `datetime.datetime` — normalise internally
- Return schema is a plain Python list of dicts — no pandas DataFrames, no numpy types in the public return value
- All numeric fields returned as Python native types (`float` for prices, `int` for volume) — no numpy int64 or float64
- Pin all direct dependencies in `requirements.txt` with exact versions
- Test file names mirror the module they test: `data/stock.py` → `tests/test_stock.py`
- Tests must not make real network calls — use `unittest.mock.patch` to mock `yfinance.Ticker`

---

## S — Safeguards

### Data Pipeline Safeguards

- Never let a raw yfinance or pandas exception propagate past `get_stock_history` — the function is the exception boundary
- Always check `df.empty` before accessing DataFrame contents — do not assume yfinance raises for bad inputs
- Never trust yfinance column name casing across versions — normalise column access using lowercase
- Always strip timezone from the DatetimeIndex before formatting dates — timezone-aware strings break downstream ISO 8601 consumers
- Always cast `volume` to Python `int` — yfinance can return float for volume on some tickers
- Pass `end_date + 1 day` to `Ticker.history()` — yfinance's `end` is exclusive; failing to correct this silently drops the last requested trading day
- Do not add fields beyond the six agreed schema keys — extra fields break schema validation in downstream consumers
- Tests must mock yfinance network calls — tests must never depend on market hours, live data, or network availability
- yfinance version must be pinned — an unpinned version allows silent breaking changes to column names or DataFrame structure

---

## Change Log
