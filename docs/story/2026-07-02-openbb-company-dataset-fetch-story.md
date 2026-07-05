# User Story: OpenBB Company Dataset Fetch
Date: 2026-07-02
Source: Pasted text

---

## Story 1: Fetch Full Company Dataset via OpenBB SDK

**As a** quantitative developer building the investment intelligence pipeline,
**I want** a function that retrieves a full company dataset for a given ticker using the OpenBB Python SDK,
**So that** downstream modules (screener, sentiment, portfolio) have a single, standardised source of fundamental and market data without duplicating API integration logic.

### Scope In
- Accept a ticker string (e.g. `"AAPL"`) as input
- Use the OpenBB Python SDK (`openbb` package) to retrieve data
- Fetch the following fields: company profile, latest price, market cap, PE ratio, EPS, revenue growth, sector, industry, analyst recommendations
- Return all data as a single standardised Python `dict` with snake_case keys
- Normalise all numeric values to Python-native `float` or `int` (no numpy scalars, no pandas objects)
- Substitute `None` for any field that is unavailable or fails to parse
- Never raise an exception to the caller — wrap all SDK calls in an exception boundary
- Live in `data/openbb_client.py` as `get_company_dataset(ticker: str) -> dict`

### Scope Out
- No caching or persistence of fetched data
- No OpenBB Hub authentication / API key management (assume key is set via `.env` / environment variable)
- No aggregation across multiple tickers (single-ticker call only)
- No historical OHLCV retrieval (that is already handled by `get_stock_history` in `data/stock.py`)
- No UI or CLI interface
- No integration with `generate_recommendation` or `analyze_sentiment` (separate story)

### Acceptance Criteria

- **Given** a valid ticker string `"AAPL"`, **when** `get_company_dataset("AAPL")` is called, **then** it returns a dict containing all nine top-level keys: `company_profile`, `latest_price`, `market_cap`, `pe_ratio`, `eps`, `revenue_growth`, `sector`, `industry`, `analyst_recommendations`
- **Given** a valid ticker, **when** the OpenBB SDK returns a value for a numeric field, **then** the returned dict contains a Python `float` or `int` — never a numpy scalar, pandas Series, or DataFrame
- **Given** a valid ticker, **when** analyst recommendations are available, **then** `analyst_recommendations` is a list of dicts, each containing at minimum `firm`, `action`, and `rating` keys
- **Given** a valid ticker, **when** analyst recommendations are not available or the SDK call fails for that field, **then** `analyst_recommendations` is `None` (not an empty list, not an exception)
- **Given** any field (e.g. `revenue_growth`) is missing from the OpenBB response or cannot be parsed, **when** the function processes that field, **then** it returns `None` for that key rather than omitting the key or raising
- **Given** an invalid or unknown ticker (e.g. `"INVALID_XYZ"`), **when** `get_company_dataset` is called, **then** it returns a dict where all values are `None` and does not raise
- **Given** the OpenBB SDK raises any exception (network error, auth error, rate limit), **when** `get_company_dataset` is called, **then** it catches the exception, logs it, and returns the all-None fallback dict

### Definition of Done
- [ ] `data/openbb_client.py` implemented with `get_company_dataset(ticker)` matching the contract above
- [ ] All numeric normalisation handled by a `_safe_float` / `_safe_int` helper (consistent with `data/stock.py` pattern)
- [ ] `_EMPTY_DATASET` module-level constant defines the fallback dict structure; returned via `.copy()` on error
- [ ] `tests/test_openbb_client.py` written with all OpenBB SDK calls mocked
- [ ] Test suite covers: happy path (all fields present), partial response (some fields None), invalid ticker, SDK exception
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_openbb_client.py -v`
- [ ] `requirements.txt` updated with `openbb` package and pinned version
- [ ] `.env.example` updated if a new environment variable is required for OpenBB auth

---

## Story 2: Standardised JSON Serialisation of Company Dataset

**As a** quantitative developer consuming the investment intelligence pipeline,
**I want** the company dataset dict to be directly serialisable to JSON without preprocessing,
**So that** I can call `json.dumps(result)` and pass the output to any downstream consumer (API, file, message queue) without transformation.

### Scope In
- Guarantee that every value in the returned dict is JSON-serialisable (`str`, `float`, `int`, `bool`, `None`, `list`, `dict`)
- Cover nested structures (e.g. `analyst_recommendations` list of dicts)
- Validate serialisability is enforced inside `get_company_dataset`, not by the caller

### Scope Out
- No custom JSON encoder class
- No file I/O — return the dict; caller decides how to persist or transmit it
- No schema validation library (e.g. Pydantic) — raw dict with documented shape is sufficient for this iteration

### Acceptance Criteria

- **Given** `get_company_dataset` returns a result, **when** `json.dumps(result)` is called on it, **then** no `TypeError` is raised
- **Given** any numeric field contains a numpy or pandas type in the raw SDK response, **when** the function processes it, **then** the returned value is a Python-native type that passes `json.dumps`
- **Given** `analyst_recommendations` is a non-empty list, **when** `json.dumps(result)` is called, **then** the nested list of dicts also serialises without error

### Definition of Done
- [ ] `test_result_is_json_serialisable` test added to `tests/test_openbb_client.py`
- [ ] Test asserts `json.dumps(result)` does not raise for both the happy-path and the all-None fallback
- [ ] All tests passing

---
