# REASONS Canvas: Get Company Fundamentals via yfinance
Date: 2026-06-30
Analysis: 2026-06-30-get-fundamentals-yfinance-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** No fundamentals retrieval function exists in the data pipeline. Downstream analytics, screening, and model-training components have no consistent, structured source for key valuation and earnings metrics per stock symbol.

**Goal:** Implement `get_fundamentals(symbol)` in `data/stock.py` that returns a Python dict with exactly five keys — `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise` — containing the latest available values from Yahoo Finance, with `None` for any missing field. The function must never raise an exception to the caller.

**Definition of Done:**
- [ ] Given a valid symbol with available data, when `get_fundamentals` is called, then the function returns a dict containing exactly the keys `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise`
- [ ] Given the returned dict, when any field has a numeric value, then that value is a Python `float` — not a numpy scalar, string, or any other type
- [ ] Given a valid symbol where one or more metrics are unavailable, when called, then affected keys are present in the returned dict with value `None` — the dict always has all five keys
- [ ] Given an invalid or unknown ticker symbol, when called, then the function returns a dict with all five keys set to `None` — no exception is raised
- [ ] Given a network failure or any yfinance exception, when called, then the function returns a dict with all five keys set to `None` — no raw exception propagates to the caller
- [ ] Given any input, when called, then the returned dict contains exactly five keys — no extra keys are ever present
- [ ] Unit tests written and passing for: all fields present, partial data (some None), invalid ticker, yfinance exception — all yfinance calls mocked

---

## E — Entities

### Data Entities

| Entity | Type | Key Fields | Relationships |
|--------|------|-----------|---------------|
| `FundamentalsRecord` | Return schema (dict) | `pe_ratio` (float or None), `pb_ratio` (float or None), `debt_to_equity` (float or None), `eps_last` (float or None), `eps_surprise` (float or None) | Produced by `get_fundamentals`; consumed by analytics, screening, and model-training modules |
| `yfinance.Ticker` | External library object | Wraps a stock symbol; exposes `.info` (fundamentals dict) and `.earnings_history` (EPS history DataFrame) | Used internally by `get_fundamentals`; not stored or passed outside the function |
| `OHLCVRecord` | Existing return schema (dict) | `date`, `open`, `high`, `low`, `close`, `volume` | Produced by the existing `get_stock_history`; unaffected by this story |

No database schema or migration is involved — this is a stateless data retrieval function with no persistence layer.

---

## A — Approach

**Pattern:** Thin stateless wrapper over an external library, with explicit schema normalisation and contract-enforced error handling — identical to the pattern already established by `get_stock_history`.

**Strategy:** Call `yfinance.Ticker(symbol).info` to retrieve a dict of valuation metrics and map four fields directly. For `eps_surprise` — absent from `.info` — access `Ticker.earnings_history` to retrieve the most recent quarter's absolute EPS difference. Wrap both accesses in a single outer try/except so any exception results in all five keys returning `None`. A private `_safe_float` helper centralises conversion of yfinance's inconsistent output types (numpy scalars, `"N/A"` strings, `None`, bare floats) to Python-native `float` or `None`. The returned dict always has exactly five keys with fixed names, enforced by explicit construction rather than dict unpacking.

**Scope In:**
- Single-symbol fundamentals retrieval via `yfinance.Ticker.info` and `Ticker.earnings_history`
- Mapping of five agreed keys: `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise`
- `_safe_float` private helper for type normalisation (shared with future use)
- All-None fallback dict on any failure or invalid input
- Unit test coverage for all acceptance criteria scenarios

**Scope Out:**
- OpenBB integration — deferred to a future story
- Additional fundamental fields beyond the five agreed keys (revenue, margins, ROE, etc.)
- Intraday or time-series fundamental data — snapshot only
- Caching or persistence of fetched fundamentals
- Batch or multi-symbol fetching
- Retry logic for network failures or rate-limiting
- Any rescaling of `debtToEquity` — raw yfinance value returned as-is

---

## S — Structure

**Module:** `data/stock.py`

**New Additions:**
- `_safe_float` private helper in `data/stock.py` — converts any yfinance value (numpy scalar, `"N/A"` string, `None`, float, int) to a Python `float` or `None`
- `get_fundamentals(symbol)` public function in `data/stock.py` — fetches `Ticker.info` for four fields, `Ticker.earnings_history` for `eps_surprise`, constructs and returns the five-key dict

**Modified Files:**
- `data/stock.py` — two additions only: `_safe_float` helper and `get_fundamentals` function appended after the existing code; no existing code is changed
- `tests/test_stock.py` — new test cases for `get_fundamentals` appended after the existing tests; no existing tests are modified

**Database:**
- None — no persistence layer in this story

---

## O — Operations

1. Add the `_safe_float(value)` private helper to `data/stock.py` — accepts any value and returns a Python `float` if the value is numeric and not the string `"N/A"`, otherwise returns `None`; must handle numpy scalar types by calling their `item()` method or wrapping in a bare `float()` cast inside a try/except

2. Add the `get_fundamentals(symbol)` public function to `data/stock.py` — wraps the entire body in a try/except that returns the all-None fallback dict on any exception; inside the try block: instantiate `yfinance.Ticker(symbol)`, access `.info` and check for an empty dict (invalid ticker guard), map `trailingPE` → `pe_ratio`, `priceToBook` → `pb_ratio`, `debtToEquity` → `debt_to_equity`, `trailingEps` → `eps_last` using `_safe_float`; then access `Ticker.earnings_history` for `eps_surprise` by taking the most recent row's `epsDifference` column value via `_safe_float`, guarding against a missing or empty DataFrame; return the explicitly constructed five-key dict

3. Write unit tests for `get_fundamentals` in `tests/test_stock.py` — tests must cover: happy path (all five fields populated with numeric values, assert each is a Python `float`), partial data (`.info` present but `earnings_history` empty — `eps_surprise` must be `None`, others must be floats), invalid ticker (`.info` returns empty dict `{}` — all five keys must be `None`), yfinance exception (`.info` raises `Exception` — all five keys must be `None`); all `yfinance.Ticker` calls must be patched with `unittest.mock.patch` — no live network calls permitted in tests

---

## N — Norms

### Python / Data Pipeline Norms

- Module layout: `data/` for retrieval and transformation logic; `tests/` for all test files
- Functions are stateless — no side effects, no module-level mutable state
- All external library exceptions are caught at the function boundary — raw third-party exceptions must never propagate to callers
- Return schema is a plain Python dict — no pandas DataFrames, no numpy types in the public return value
- All numeric fields returned as Python native types (`float` for all five fields) — no numpy int64, float64, or any other numpy/pandas wrapper
- The returned dict always has exactly the contracted keys — callers must never need to guard against `KeyError`
- Private helpers are prefixed with `_` — not part of the public module API
- Pin all direct dependencies in `requirements.txt` with exact versions
- Test file names mirror the module they test: `data/stock.py` → `tests/test_stock.py`
- Tests must not make real network calls — use `unittest.mock.patch` to mock `yfinance.Ticker`
- Do not add comments explaining what the code does — only add comments when the WHY is non-obvious

---

## S — Safeguards

### Data Pipeline Safeguards

- Never let a raw yfinance or pandas exception propagate past `get_fundamentals` — the function is the exception boundary
- Always check for an empty `.info` dict before accessing keys — do not assume yfinance raises for bad or delisted tickers
- Never trust yfinance value types — always pass through `_safe_float` before returning; never cast with bare `float()` outside the helper
- Always treat the string `"N/A"` as `None` — a bare `float("N/A")` raises `ValueError` and must be caught inside `_safe_float`
- Always guard `Ticker.earnings_history` access — the attribute may not exist or may return an empty DataFrame for non-US tickers or recently listed companies; fall back to `None` for `eps_surprise` rather than raising
- Never return a dict with fewer or more than the five agreed keys — construct the return dict explicitly with all five keys, not via dict spread or unpacking
- Do not rescale `debtToEquity` — return the raw yfinance value; document that it may be expressed as a percentage by yfinance (e.g. `30.0` meaning 30%) rather than a decimal ratio
- Tests must mock yfinance network calls — tests must never depend on market hours, live data, or network availability

---

## Change Log

[Appended by /prompt-update and /sync]
