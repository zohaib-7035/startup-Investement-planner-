# Analysis: OpenBB Company Dataset Fetch
Date: 2026-07-02
Story: 2026-07-02-openbb-company-dataset-fetch-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline — no web framework, no ORM, no persistence layer. Three existing data modules follow a strict module-per-concern pattern: `data/stock.py` (yfinance market data), `data/sentiment.py` (Anthropic LLM sentiment), `data/screener.py` (pure-Python rule engine). Key integrations: `yfinance==0.2.40`, `anthropic==0.40.0`, `pandas==2.2.2`, `numpy==1.26.4`. `openbb` is not yet installed. No frontend. Test suite uses `unittest.mock.patch` throughout; 50 tests, all passing.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_safe_float(value)` helper | `data/stock.py:66` | Returns `float` or `None`; handles numpy scalars, `None`, non-numeric strings. The new module needs its own copy — modules are kept independent |
| Exception boundary pattern | `data/stock.py:23`, `data/sentiment.py:41` | Outer `try/except Exception` wraps all external calls; returns fallback `.copy()` on any failure |
| Module-level fallback constant | `data/sentiment.py:14–15` | `_EMPTY_INPUT_FALLBACK` / `_API_FAILURE_FALLBACK` as module-level dicts; returned via `.copy()`. This is the pattern for `_EMPTY_DATASET` |
| Per-field inner `try/except` pattern | `data/stock.py:90–95` | `eps_surprise` has its own nested try/except so a secondary call failure doesn't abort the whole response. This pattern must be applied to every OpenBB endpoint call |
| `yf.Ticker` mock pattern | `tests/test_stock.py:32–35` | `patch("data.stock.yf.Ticker", return_value=mock_instance)` — same approach applies to OpenBB client instantiation |
| Numpy scalar test | `tests/test_stock.py:256–269` | `np.float64` passed into mock; result asserted as `type(...) is float`. Must replicate for OpenBB fields |
| `json.dumps` serialisability | implicit in pipeline | All existing modules return Python-native types; no explicit serialisability test exists yet — Story 2 adds this gap |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/openbb_client.py` | New module | Does not exist — entirely new file |
| `get_company_dataset(ticker)` | Public function | Entry point; wraps all OpenBB calls |
| `_EMPTY_DATASET` | Module-level constant | All-None dict with all 9 keys; returned via `.copy()` on total failure |
| `_safe_float` (local copy) | Private helper | Copy from `data/stock.py` — do not import across modules |
| `_parse_recommendations(raw)` | Private helper | Normalises raw OpenBB recommendations response into `list[dict]` with `firm`, `action`, `rating` keys, or `None` |
| `tests/test_openbb_client.py` | New test file | All OpenBB SDK calls must be mocked |
| `openbb` package | `requirements.txt` entry | Not yet installed — version must be pinned |

---

## Strategic Approach

Follow the same module-per-concern pattern established by `data/stock.py` and `data/sentiment.py`. The new `data/openbb_client.py` makes multiple OpenBB endpoint calls (profile, quote, metrics, recommendations), each individually wrapped in its own `try/except` block so a single endpoint failure produces `None` for that field rather than aborting the entire response. A single outer `try/except` acts as a final safety net and returns `_EMPTY_DATASET.copy()` if instantiation or a catastrophic shared call fails. The `_parse_recommendations` helper isolates the more complex list-normalisation logic from the main function body, consistent with how `_parse_llm_response` in `data/sentiment.py` isolates JSON parsing.

---

## Key Design Decisions

- **Per-field exception isolation, not a single outer try:** Each OpenBB endpoint call (`profile`, `quote`, `metrics`, `recommendations`) gets its own `try/except` block that catches independently and assigns `None`. This is already established by the `eps_surprise` inner try in `data/stock.py:90–95`. Without this, one failing endpoint (e.g. rate-limited recommendations) would wipe out all other successfully fetched fields.

- **`_safe_float` copied, not imported:** Existing modules each own their `_safe_float`. Do not create a shared `data/utils.py` — the architecture rule says no cross-module imports, and the function is 6 lines. Copy it verbatim.

- **`company_profile` as a nested dict, not a flat field:** The story lists `sector` and `industry` as separate top-level keys AND as part of `company_profile`. Resolution: `company_profile` holds descriptive string fields (name, description, CEO, employees, address); `sector` and `industry` are promoted to the top level for easy access by the screener and other consumers. Avoids ambiguity about where downstream code should look.

- **OpenBB provider dependency:** OpenBB v4 requires a provider (e.g. `yfinance`, `fmp`). Since `yfinance` is already installed, defaulting to `provider="yfinance"` in each call avoids requiring a new API key. If the provider is absent or fails, the per-field try/except catches it and returns `None`.

- **Mock strategy:** Patch the `openbb.Python` client class (or the `obb` module-level object) at import time, not at the HTTP layer. Same pattern as `patch("data.stock.yf.Ticker", ...)` in `test_stock.py`.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| OpenBB SDK returns `OBBject` wrapper, not a plain dict | High | Every `.results` access returns a Pydantic model or list of models, not a raw dict. `_safe_float` must handle Pydantic model attribute access (e.g. `result.results[0].pe_ratio`) — confirm by inspecting the SDK response shape during implementation |
| OpenBB v3 vs v4 API surface is completely different | High | v4 uses `obb.equity.profile()`, `obb.equity.price.quote()` etc. v3 uses a different namespace. Pin the version in `requirements.txt` and document which namespace is assumed |
| Multiple SDK calls increase surface for partial failures | Medium | 3–4 separate endpoint calls per `get_company_dataset` invocation. The per-field try/except pattern mitigates this, but tests must cover the partial-failure case (some fields present, others None) |
| `analyst_recommendations` structure varies by provider | Medium | Field names (`firm`, `action`, `rating`) may differ across OpenBB providers. `_parse_recommendations` must use `.get()` with `None` fallbacks, not direct key access |
| `revenue_growth` may require an income statement call | Medium | It is not typically in the quote or profile endpoint — may require `obb.equity.fundamental.income()` which adds a 4th call and potential auth/rate-limit risk |
| `company_profile` vs `sector`/`industry` key overlap | Low | Both could source from the same OpenBB profile call. Mitigated by Decision 3 above — profile is nested, sector/industry are promoted to top level |
| `_safe_float` applied to string `"N/A"` or `"--"` from OpenBB | Low | `_safe_float` already handles strings by returning `None` (existing behaviour in `data/stock.py:67`). Verified safe |
| Python 3.9 — no `X \| Y` union hints in signatures | Low | Existing constraint. Use `"float \| None"` as string annotation, or `Union[float, None]` — same as current modules |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Valid ticker returns dict with all 9 keys | Needs work | New function; pattern for returning a fixed-key dict is established by `get_fundamentals` |
| Numeric fields are Python-native float/int | Supported pattern | `_safe_float` exists in `data/stock.py` — copy to new module |
| `analyst_recommendations` is list of dicts with firm/action/rating | Needs work | Requires new `_parse_recommendations` helper; no precedent in codebase for list-valued fields |
| `analyst_recommendations` is `None` when unavailable | Needs work | Must be handled in `_parse_recommendations`: empty or failed call → `None`, not `[]` |
| Missing scalar field returns `None`, key still present | Supported pattern | `_safe_float` returns `None`; `get_fundamentals` demonstrates this for 5 keys |
| Invalid ticker → all-None dict, no exception | Supported pattern | `_EMPTY_DATASET.copy()` mirrors `get_fundamentals` invalid-ticker path |
| SDK exception → all-None dict, no exception | Supported pattern | Outer `try/except Exception` mirrors `data/stock.py:23` and `data/sentiment.py:41` |
| `json.dumps(result)` does not raise (Story 2) | Partially supported | Scalar fields are safe via `_safe_float`. `company_profile` (nested dict) and `analyst_recommendations` (list of dicts) must also contain only JSON-native types — `_parse_recommendations` must enforce this |

---

## Dependencies

- `data/stock.py` — `_safe_float` pattern copied from here; no import dependency
- `requirements.txt` — must add `openbb` with pinned version
- `.env.example` — add `OPENBB_TOKEN` if Hub authentication is needed (scope-out for this story, but note the env var in example for future)
- `tests/test_openbb_client.py` — new file; imports from `data.openbb_client` only
