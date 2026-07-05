# Analysis: Improve Stock Data Pipeline Test Quality
Date: 2026-06-30
Story: 2026-06-30-improve-stock-data-test-quality-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

This is a greenfield Python data-pipeline project with no web framework, ORM, or persistence layer. The module layout follows a two-package convention: `data/` for retrieval and transformation logic (`get_stock_history`, `get_fundamentals`, `_safe_float`, `_parse_date`, `_to_date_str`), and `tests/` for all test files (`tests/test_stock.py`). The test suite uses `unittest.mock.patch` to mock all yfinance network calls — no live requests are made during testing. Dependencies are pinned at `yfinance==0.2.40`, `pandas==2.2.2`, `numpy==1.26.4`, and `pytest==8.2.2`. There is no frontend stack. All three story improvements have already been implemented in the current working state of the codebase.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `test_accepts_date_objects_as_input` | `tests/test_stock.py` | Date-input-type test — now includes `assert result[0]["date"] == "2024-01-02"` |
| `test_accepts_datetime_objects_as_input` | `tests/test_stock.py` | Datetime-input-type test — now includes `assert result[0]["date"] == "2024-01-02"` |
| `test_fundamentals_eps_surprise_uses_most_recent_earnings_row` | `tests/test_stock.py` | Replacement for the removed redundant test; exercises `.iloc[-1]` selection with two-row `earnings_history` |
| `test_fundamentals_all_numeric_values_are_python_float` | `tests/test_stock.py` | Existing type-assertion test using Python float literals — retained unchanged |
| `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` | `tests/test_stock.py` | New test using `numpy.float64` mock values to exercise `_safe_float`'s numpy unwrapping path |
| `_safe_float` helper | `data/stock.py` | Private helper that converts any yfinance value to Python `float` or `None` — the primary production path exercised by the numpy test |
| `_parse_date` / `_to_date_str` helpers | `data/stock.py` | Date normalisation utilities — the primary production path validated by the strengthened date-input-type tests |
| `_make_earnings_history` test helper | `tests/test_stock.py` | Builds a `pd.DataFrame` with `epsDifference` column — used by both the partial-data and multi-row eps_surprise tests |
| `_mock_fundamentals_ticker` test helper | `tests/test_stock.py` | Returns a `MagicMock` with `.info` and `.earnings_history` attributes set — shared by all `get_fundamentals` tests |
| `numpy==1.26.4` | `requirements.txt` | Newly pinned as a direct test dependency — previously a transitive dependency of pandas only |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `test_fundamentals_returns_exactly_five_keys` | Test method (removed) | Correctly removed — assertion implied entirely by `test_fundamentals_returns_correct_schema`'s set equality check |

---

## Strategic Approach

All three improvements are assertion-depth and coverage-gap fixes within the existing test file — no implementation code is touched. The approach is conservative: strengthen existing tests in-place (date-input-type tests), swap one redundant test for a higher-value replacement that covers an untested code path (`.iloc[-1]` selection), and add one new test that uses actual `numpy.float64` values to exercise the production data type that `_safe_float` was written to handle. The numpy import is the only new external dependency introduced; it is pinned in `requirements.txt` as a direct dependency to make the reliance explicit and version-stable.

---

## Key Design Decisions

- **Strengthen rather than replace date-input-type tests** — the mock setup and structure are correct; only the assertion depth was insufficient. Replacing the tests entirely would have required restructuring the mock, which is unnecessary.
- **Remove `test_fundamentals_returns_exactly_five_keys` rather than keeping both** — a redundant test that never provides an independent failure mode actively harms the suite by adding maintenance cost and inflating passing-test counts without adding coverage.
- **New eps_surprise multi-row test uses the simplest possible mock** — two rows with different values in order; the assertion is a direct value check, not a structural check. This is sufficient to prove `.iloc[-1]` is in use.
- **numpy scalar test asserts only the two most at-risk fields** — `pe_ratio` (from `.info`) and `eps_surprise` (from `earnings_history`) cover both retrieval paths. Asserting all five fields would be redundant with `test_fundamentals_all_numeric_values_are_python_float`.
- **Pin numpy at `1.26.4`** — the latest 1.x release compatible with `pandas==2.2.2`; avoids pulling an unvetted version on clean installs.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| numpy version incompatibility with pandas==2.2.2 | Medium | numpy 1.26.4 is the tested compatible version; numpy 2.x introduced breaking changes in some pandas integrations — the pin prevents accidental upgrade |
| `_make_earnings_history` row order assumption | Low | The multi-row test relies on `pd.DataFrame` preserving insertion order (guaranteed in pandas ≥ 1.0); `.iloc[-1]` will always select the last inserted row |
| Unused `pytest` import | Low | `pytest` is imported but no `@pytest.mark.*` decorators or `pytest.raises` calls exist in the file; safe to remove in a future cleanup but not a functional risk |
| Date-value assertion assumes mock date matches input date | Low | The mock always returns `"2024-01-02"` regardless of the parsed input — the test proves the function returned *a* result for that input, not that it forwarded the *correct* date range to yfinance. A more complete assertion would verify the `history()` call arguments, but that is out of scope for this story. |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| `test_accepts_date_objects_as_input` asserts both len and date string value | Supported | Implemented — `assert result[0]["date"] == "2024-01-02"` added |
| `test_accepts_datetime_objects_as_input` asserts both len and date string value | Supported | Implemented — `assert result[0]["date"] == "2024-01-02"` added |
| A bug in `_parse_date` returning the wrong date would cause these tests to fail | Supported | The date-value assertion directly catches this regression |
| `earnings_history` with two rows → `eps_surprise` is the value from the last row | Supported | Implemented — `_make_earnings_history([{"epsDifference": 0.05}, {"epsDifference": 0.20}])`, assert `== 0.20` |
| `test_fundamentals_returns_exactly_five_keys` removed | Supported | Removed — replaced by the multi-row eps_surprise test |
| `numpy.float64` `.info` values → returned dict values are Python `float` | Supported | Implemented — `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` passes `np.float64` values and asserts `type(...) is float` |
| `numpy` pinned as direct dependency in `requirements.txt` | Supported | `numpy==1.26.4` added |
| All existing tests continue to pass with no regressions | Supported | No production code was changed; mock contracts are unchanged |

---

## Dependencies

- **`data/stock.py`** — read-only reference; `_safe_float` and `_parse_date` are the functions under test; no changes made to this file
- **`tests/test_stock.py`** — the sole file modified; three changes: two assertion additions, one test replacement, one new test, one new import
- **`requirements.txt`** — `numpy==1.26.4` added as a direct dependency
- **`numpy==1.26.4`** — new direct test dependency; previously transitive via pandas
