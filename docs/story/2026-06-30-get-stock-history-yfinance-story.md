# User Story: Get Stock History via yfinance
Date: 2026-06-30
Source: Pasted text

---

## Story 1: Retrieve Daily Historical OHLCV Stock Data

**As a** system (financial data pipeline consumer),
**I want** a function `get_stock_history(symbol, start_date, end_date)` that fetches daily OHLCV data for a given stock symbol and date range using yfinance,
**So that** downstream analytics, charting, and model-training components receive consistently structured, date-sorted price data.

### Scope In
- Accept `symbol` (string), `start_date` (string or date), `end_date` (string or date) as parameters
- Use `yfinance` to fetch daily-interval historical data
- Return a Python list of dicts, each containing exactly: `date`, `open`, `high`, `low`, `close`, `volume`
- `date` field formatted as ISO 8601 string (e.g. `"2024-01-15"`)
- List sorted ascending by date
- Empty list returned when no data exists for the given range

### Scope Out
- No intraday (sub-daily) resolution — defer to a future story
- No adjusted-close or dividend/split data fields in this iteration
- No caching or persistence of fetched data
- No support for batch/multi-symbol fetching in a single call

### Acceptance Criteria
- Given a valid symbol (e.g. `"AAPL"`) and a date range with known trading days, when `get_stock_history("AAPL", "2024-01-01", "2024-01-31")` is called, then the function returns a non-empty list where every item has exactly the keys `date`, `open`, `high`, `low`, `close`, `volume`
- Given the returned list, when items are iterated, then dates are in strict ascending order with no duplicates
- Given `start_date == end_date` on a valid trading day, when called, then the list contains exactly one record for that day
- Given `start_date == end_date` on a weekend or market holiday, when called, then the list is empty (no error raised)
- Given an invalid or unknown ticker symbol, when called, then the function either returns an empty list or raises a `ValueError` with a descriptive message — it must not raise an unhandled `yfinance`-level exception
- Given a date range entirely in the future, when called, then the function returns an empty list

### Definition of Done
- [ ] Implementation complete and peer-reviewed
- [ ] Unit tests written for: happy path, empty range, weekend-only range, invalid ticker
- [ ] Return schema validated (correct keys, ascending sort) in tests
- [ ] No regression in any existing data-fetching flows
- [ ] Product/requester has reviewed and confirmed the output structure matches downstream expectations
- [ ] QA sign-off complete
