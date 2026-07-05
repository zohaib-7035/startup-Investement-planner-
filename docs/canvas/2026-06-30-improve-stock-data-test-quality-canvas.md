# REASONS Canvas: Improve Stock Data Pipeline Test Quality
Date: 2026-06-30
Analysis: 2026-06-30-improve-stock-data-test-quality-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** Three quality gaps exist in `tests/test_stock.py`: two date-input-type tests assert only that a result was returned but not that the correct date was produced (a silent regression in `_parse_date` would pass them), one test adds no independent failure mode over an existing set-equality check (redundant count assertion), and no test exercises the numpy scalar type-conversion path in `_safe_float` despite that being the dominant real-world input type from yfinance.

**Goal:** Strengthen the two date-input-type tests with date-value assertions, replace the redundant five-key count test with a multi-row `eps_surprise` test that exercises the `.iloc[-1]` selection logic, and add a numpy scalar type-conversion test that passes `numpy.float64` values through `get_fundamentals` and asserts bare Python `float` is returned. Pin `numpy` as a direct dependency in `requirements.txt`.

**Definition of Done:**
- [ ] Given `test_accepts_date_objects_as_input` passes `datetime.date(2024, 1, 2)` as input, when the test runs, then it asserts both `len(result) == 1` and `result[0]["date"] == "2024-01-02"`
- [ ] Given `test_accepts_datetime_objects_as_input` passes `datetime.datetime(2024, 1, 2, 9, 30)` as input, when the test runs, then it asserts both `len(result) == 1` and `result[0]["date"] == "2024-01-02"`
- [ ] Given a bug in `_parse_date` that returns the wrong date, when these tests run, then they fail — not pass silently
- [ ] Given `earnings_history` contains two rows with `epsDifference` values `[0.05, 0.20]` (older first), when `get_fundamentals` is called, then `result["eps_surprise"]` equals `0.20`
- [ ] Given `test_fundamentals_returns_exactly_five_keys` is removed, when the test suite runs, then no coverage gap exists — the set-equality check in `test_fundamentals_returns_correct_schema` continues to guarantee the key contract
- [ ] Given `Ticker.info` returns `numpy.float64` values for all four mapped fields and `earnings_history` contains a `numpy.float64` `epsDifference`, when `get_fundamentals` is called, then `type(result["pe_ratio"]) is float` and `type(result["eps_surprise"]) is float` both pass
- [ ] Given `numpy` is added to `requirements.txt`, when the test suite is installed and run in a clean environment, then the import resolves without error
- [ ] All 19 tests pass with no regressions

---

## E — Entities

### Test Artifacts

| Artifact | Type | Location | Change |
|----------|------|----------|--------|
| `test_accepts_date_objects_as_input` | Existing test — strengthened | `tests/test_stock.py` | Date-value assertion added |
| `test_accepts_datetime_objects_as_input` | Existing test — strengthened | `tests/test_stock.py` | Date-value assertion added |
| `test_fundamentals_returns_exactly_five_keys` | Existing test — removed | `tests/test_stock.py` | Redundant; implied by set-equality check |
| `test_fundamentals_eps_surprise_uses_most_recent_earnings_row` | New test | `tests/test_stock.py` | Two-row `earnings_history` mock; assert `.iloc[-1]` value used |
| `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` | New test | `tests/test_stock.py` | `numpy.float64` mock values; assert output is Python `float` |
| `_safe_float` | Existing helper — under test | `data/stock.py` | No changes; numpy path exercised for first time |
| `_parse_date` / `_to_date_str` | Existing helpers — under test | `data/stock.py` | No changes; date-value assertions now catch regressions |
| `numpy==1.26.4` | New direct dependency | `requirements.txt` | Pinned; previously transitive via pandas |

No database schema or production code is involved — this is a test-only quality improvement with one dependency pin.

---

## A — Approach

**Pattern:** In-place assertion strengthening and targeted test replacement — no new production code, no structural test refactoring.

**Strategy:** Each of the three improvements is the minimum change needed to close a specific gap: add one assertion to each date-input test, swap one redundant test for a higher-value replacement that covers the `.iloc[-1]` selection path, and add one new test that passes real `numpy.float64` values through `_safe_float` to prove the numpy unwrapping path. The `numpy` import is the only new external dependency, and it is pinned explicitly to prevent accidental upgrade to numpy 2.x which introduced breaking changes in some pandas integrations.

**Scope In:**
- Date-value assertion added to `test_accepts_date_objects_as_input` and `test_accepts_datetime_objects_as_input`
- `test_fundamentals_returns_exactly_five_keys` removed and replaced with `test_fundamentals_eps_surprise_uses_most_recent_earnings_row`
- `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` added
- `import numpy as np` added to `tests/test_stock.py`
- `numpy==1.26.4` added to `requirements.txt`

**Scope Out:**
- No changes to `data/stock.py` — production code is not touched
- No verification that the correct date range is forwarded to `yfinance.Ticker.history()` call arguments — that requires `mock.history.call_args` assertions and is deferred to a future story
- No removal of the unused `pytest` import — minor cleanup deferred
- No changes to any other test method or helper function

---

## S — Structure

**Module:** `tests/test_stock.py`

**New Files:**
- None

**Modified Files:**
- `tests/test_stock.py` — two assertion additions (date-value), one test removed, one test added (multi-row eps_surprise), one test added (numpy scalar), one import added (`numpy`)
- `requirements.txt` — `numpy==1.26.4` added as a pinned direct dependency

**Database:**
- None

---

## O — Operations

1. Add `import numpy as np` to `tests/test_stock.py` and pin `numpy==1.26.4` in `requirements.txt` — establishes the direct dependency before any test references it

2. Strengthen `test_accepts_date_objects_as_input` in `tests/test_stock.py` — add `assert result[0]["date"] == "2024-01-02"` after the existing `assert len(result) == 1` so a `_parse_date` regression that returns the wrong date causes a test failure

3. Strengthen `test_accepts_datetime_objects_as_input` in `tests/test_stock.py` — same assertion as above; the mock returns `"2024-01-02"` and the datetime input resolves to the same date

4. Replace `test_fundamentals_returns_exactly_five_keys` with `test_fundamentals_eps_surprise_uses_most_recent_earnings_row` in `tests/test_stock.py` — mock `_make_earnings_history` with two rows (`epsDifference: 0.05` then `epsDifference: 0.20`), assert `result["eps_surprise"] == 0.20` to prove `.iloc[-1]` selects the most recent row

5. Add `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` to `tests/test_stock.py` — mock all four `Ticker.info` fields and `epsDifference` as `numpy.float64` values; assert `type(result["pe_ratio"]) is float` and `type(result["eps_surprise"]) is float` to prove `_safe_float` unwraps numpy scalars to Python-native types

---

## N — Norms

### Python / Data Pipeline Test Norms

- Tests must not make real network calls — all yfinance calls must be patched with `unittest.mock.patch`
- Test helpers (`_make_df`, `_make_earnings_history`, `_mock_ticker`, `_mock_fundamentals_ticker`) are module-level functions prefixed with `_`; they are not test methods and must not be named `test_*`
- Each test method must assert both the shape (schema / key set) and the specific value or type being validated — asserting only count or only schema is insufficient
- Test names must describe the scenario under test, not the action: `test_eps_surprise_uses_most_recent_earnings_row` not `test_iloc`
- All direct dependencies must be pinned with exact versions in `requirements.txt` — no unpinned or range-pinned dependencies
- The `pytest` import should be present only if `@pytest.mark.*` decorators or `pytest.raises` are used
- No test method may depend on execution order or shared mutable state

---

## S — Safeguards

### Data Pipeline Test Safeguards

- Never modify `data/stock.py` as part of a test-quality improvement — production code changes require their own story and canvas
- Never assert only count (`len`) without also asserting content — a count assertion alone cannot catch schema or value regressions
- Always use the most realistic mock data type available: prefer `numpy.float64` over Python `float` when testing `_safe_float`, because that is what yfinance actually returns via pandas
- Pin numpy at a version known to be compatible with the pinned pandas version — numpy 2.x introduced breaking changes; 1.26.4 is the stable 1.x release compatible with pandas 2.2.2
- Do not keep redundant tests that assert a condition already fully implied by another assertion in the same test suite — they inflate passing-test counts without adding coverage
- When replacing a test, ensure the replacement covers a code path the removed test did not cover — a test swap must add net coverage, not just reword the same assertion

---

## Change Log

[Appended by /prompt-update and /sync]
