# Analysis: Get Company Fundamentals via yfinance
Date: 2026-06-30
Story: 2026-06-30-get-fundamentals-yfinance-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

This is a greenfield Python data-pipeline project with no web framework, ORM, or persistence layer. The module layout follows a two-package convention: `data/` for retrieval and transformation logic, `tests/` for all test files. The sole existing implementation is `data/stock.py`, which exports `get_stock_history` — a thin, stateless wrapper over `yfinance.Ticker.history()` that normalises a pandas DataFrame into a list of OHLCV dicts. All exceptions are caught at the function boundary; downstream callers receive only clean Python types. Dependencies are pinned at `yfinance==0.2.40`, `pandas==2.2.2`, and `pytest==8.2.2`. There is no frontend stack.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `get_stock_history` function | `data/stock.py` | Established pattern for yfinance wrapper: exception boundary, schema normalisation, native-type casting, empty-list fallback |
| `_parse_date` / `_to_date_str` helpers | `data/stock.py` | Private date normalisation utilities — may be reused or referenced |
| `yfinance.Ticker` | Runtime (yfinance==0.2.40) | Primary data retrieval object; `.history()` already used; `.info` and `.earnings_history` are available surfaces for fundamentals |
| `unittest.mock.patch` test pattern | `tests/test_stock.py` | Established mocking convention — all yfinance calls are patched, no live network calls in tests |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `get_fundamentals` function | Python function | Core deliverable — does not exist yet; to be added to `data/stock.py` to keep the data module unified |
| `.info` dict normaliser | Logic inside `get_fundamentals` | Maps yfinance `Ticker.info` keys → `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`; handles missing or `"N/A"` string values |
| `eps_surprise` retriever | Logic inside `get_fundamentals` | `eps_surprise` is not in `.info`; requires a separate access to `Ticker.earnings_history` DataFrame — most recent row's `epsDifference` column |
| `_safe_float` helper | Private utility | Converts any value (float, int, `"N/A"`, `None`, numpy scalar) to a Python `float` or `None`; reusable across both functions |
| Unit tests for `get_fundamentals` | `tests/test_stock.py` | Must cover: all fields present, partial data (some None), invalid ticker, yfinance exception — all mocked |

---

## Strategic Approach

Add `get_fundamentals` to `data/stock.py` as a sibling of `get_stock_history`, following the same thin-wrapper pattern already established. The function calls `yfinance.Ticker(symbol).info` to obtain a dict of valuation metrics, then maps four of the five fields directly. For `eps_surprise` — which is absent from `.info` — it makes a second access to `Ticker.earnings_history` to retrieve the most recent quarter's EPS difference. Both calls are wrapped in a single try/except so any yfinance or network failure returns the full five-key dict with all values as `None`. A private `_safe_float` helper centralises the conversion of yfinance's inconsistent value types (numpy scalars, `"N/A"` strings, `None`) into Python-native `float` or `None`.

---

## Key Design Decisions

- **Place `get_fundamentals` in `data/stock.py`, not a new file** — the module is intentionally the single stable interface for all stock data retrieval; a second file would fragment the public API without adding structure.
- **Use `Ticker.info` for four fields, `Ticker.earnings_history` for `eps_surprise`** — `info` is the canonical yfinance fundamentals surface; `earnings_history` is the only reliable source for per-quarter EPS actuals vs. estimates in version 0.2.40.
- **Map `eps_surprise` to the absolute difference (`epsDifference`), not `surprisePercent`** — absolute EPS difference matches the expected output format shown in the story (`0.12`); percentage would need a division and produces a different scale.
- **Always return all five keys** — even on total failure, the dict shape is fixed; callers must never guard against `KeyError`.
- **Do not re-raise or log** — consistent with the existing `get_stock_history` contract; the function is the exception boundary.
- **Pin no new dependencies** — `yfinance.Ticker.info` and `.earnings_history` are available in the already-pinned `yfinance==0.2.40`; no additions to `requirements.txt` are needed.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| `eps_surprise` unavailable via `.info` — requires separate `earnings_history` access | High | Must access `Ticker.earnings_history` DataFrame separately; if empty or missing `epsDifference` column, return `None` for that key only |
| `Ticker.info` returns empty dict `{}` for invalid or delisted tickers — no exception raised | High | Must check for empty dict or missing keys explicitly — cannot rely on try/except alone |
| Some `.info` values are the string `"N/A"` rather than `None` or a numeric type | High | `_safe_float` must treat `"N/A"` as `None`; a naive `float()` cast on `"N/A"` raises `ValueError` |
| `Ticker.info` values may be numpy scalar types (e.g. `numpy.float64`) | Medium | `_safe_float` must unwrap numpy scalars to Python `float` before returning — numpy types break JSON serialisation and downstream type checks |
| `debtToEquity` in yfinance is sometimes expressed as a percentage (e.g. `30.0` meaning 30%) rather than a ratio (`0.30`) | Medium | Document the raw yfinance value is returned as-is; do not silently rescale — let the caller decide if normalisation is needed |
| `Ticker.earnings_history` may not exist for non-US tickers or newly listed companies | Medium | Wrap access in try/except and fall back to `None` for `eps_surprise` if the attribute is missing or the DataFrame is empty |
| `Ticker.info` HTTP call is significantly slower than `Ticker.history()` | Low | No retry logic in scope; document as a known latency characteristic; out of scope for caching in this story |
| yfinance rate-limiting or network failure during `.info` or `.earnings_history` access | Low | Caught by the outer try/except; all five fields return `None` |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Valid symbol → dict with exactly keys `pe_ratio`, `pb_ratio`, `debt_to_equity`, `eps_last`, `eps_surprise` | Needs work | No implementation exists; straightforward with `.info` + `.earnings_history` |
| Any numeric value is a Python `float` (not numpy or string) | Needs work | Requires `_safe_float` helper to normalise yfinance's mixed output types |
| Missing field → key present with value `None`, dict still has all five keys | Needs work | Must guard against missing `.info` keys and empty `.earnings_history` |
| Invalid ticker → all five keys `None`, no exception | Needs work | yfinance returns `{}` for bad tickers; explicit empty-dict guard required |
| yfinance exception → all five keys `None`, no exception propagates | Needs work | Outer try/except covers this; consistent with `get_stock_history` pattern |
| Returned dict has exactly five keys — no extras | Needs work | Explicit dict construction with fixed keys ensures this |

---

## Dependencies

- **`yfinance==0.2.40`** — `Ticker.info` (fundamentals dict) and `Ticker.earnings_history` (EPS surprise); already pinned
- **`data/stock.py`** — `get_fundamentals` added as a sibling function; `_safe_float` added as a shared private helper
- **`tests/test_stock.py`** — new test cases appended; existing `_make_df` and `_mock_ticker` helpers may be extended or mirrored for `.info` / `.earnings_history` mocking
- **Downstream consumers (future)** — analytics, screening, and model-training pipelines (out of scope; `get_fundamentals` is their input boundary)
