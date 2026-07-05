# User Story: Get Company Fundamentals via yfinance
Date: 2026-06-30
Source: Pasted text

---

## Story 1: Retrieve Key Fundamental Metrics for a Stock Symbol

**As a** system (financial data pipeline consumer),
**I want** a function `get_fundamentals(symbol)` that fetches the latest available fundamental data for a given stock symbol using Yahoo Finance (yfinance),
**So that** downstream analytics, screening, and model-training components receive a consistently structured dict of valuation and earnings metrics without needing to know the data source internals.

### Scope In
- Accept `symbol` (string) as the sole parameter
- Use `yfinance.Ticker` to retrieve fundamental data
- Return a Python dict with exactly these keys: `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise`
- Return `None` (Python null) for any key whose value is unavailable or cannot be determined
- All returned numeric values are Python native types (`float` or `None`)
- Invalid tickers, network failures, or missing data fields must never raise an unhandled exception — return the dict with affected keys set to `None`

### Scope Out
- No support for batch / multi-symbol fetching in a single call — defer to a future story
- No intraday or time-series fundamental data — only the latest available snapshot
- No caching or persistence of fetched data
- No additional fundamental fields beyond the five agreed keys (e.g. revenue, margins, ROE) — defer to a future story
- No OpenBB integration in this iteration — Yahoo Finance is the sole data source

### Acceptance Criteria
- Given a valid symbol (e.g. `"AAPL"`) with available data, when `get_fundamentals("AAPL")` is called, then the function returns a dict containing exactly the keys `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise`
- Given the returned dict, when any field has a numeric value, then that value is a Python `float` (not a numpy float or string)
- Given a valid symbol where one or more metrics are unavailable (e.g. company has no debt), when called, then the affected keys are present in the returned dict with value `None` — the dict always has all five keys
- Given an invalid or unknown ticker symbol, when called, then the function returns a dict with all five keys set to `None` — no exception is raised
- Given a network failure or yfinance exception during the call, when called, then the function returns a dict with all five keys set to `None` — no raw exception propagates to the caller
- Given any valid or invalid input, when called, then the returned dict contains exactly five keys — no extra keys are ever present

### Definition of Done
- [ ] Implementation complete and peer-reviewed
- [ ] Unit tests written for: happy path (all fields present), partial data (some fields `None`), invalid ticker, yfinance exception
- [ ] Return schema validated (correct keys, correct types) in tests
- [ ] All yfinance calls mocked in tests — no live network calls in the test suite
- [ ] No regression in existing `get_stock_history` flows
- [ ] Product/requester has reviewed and confirmed the output structure matches downstream expectations
- [ ] QA sign-off complete

---
