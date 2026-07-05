# User Story: Improve Stock Data Pipeline Test Quality
Date: 2026-06-30
Source: Pasted text

---

## Story 1: Strengthen Date-Input-Type Test Assertions

**As a** system (data pipeline quality gate),
**I want** the date-input-type tests for `get_stock_history` to assert the actual parsed date value in the result — not only that a result was returned,
**So that** a silent regression in `_parse_date` or `_to_date_str` that produces a wrong date string cannot pass these tests undetected.

### Scope In
- Add `assert result[0]["date"] == "2024-01-02"` to `test_accepts_date_objects_as_input`
- Add `assert result[0]["date"] == "2024-01-02"` to `test_accepts_datetime_objects_as_input`
- No change to mock setup or test structure — assertion-only change

### Scope Out
- No changes to `get_stock_history` implementation
- No new test cases — only strengthening the two existing ones
- No changes to any other test method

### Acceptance Criteria
- Given `test_accepts_date_objects_as_input` passes a `datetime.date(2024, 1, 2)` input, when the test runs, then it asserts both `len(result) == 1` and `result[0]["date"] == "2024-01-02"`
- Given `test_accepts_datetime_objects_as_input` passes a `datetime.datetime(2024, 1, 2, 9, 30)` input, when the test runs, then it asserts both `len(result) == 1` and `result[0]["date"] == "2024-01-02"`
- Given a bug is introduced in `_parse_date` that returns the wrong date, when these tests run, then they fail — not pass silently

### Definition of Done
- [ ] Both date-input-type tests assert the returned date string value
- [ ] All existing tests continue to pass with no regressions
- [ ] No changes made outside `tests/test_stock.py`

---

## Story 2: Replace Redundant Key-Count Test with Multi-Row eps_surprise Test

**As a** system (data pipeline quality gate),
**I want** `test_fundamentals_returns_exactly_five_keys` replaced with a test that verifies `get_fundamentals` reads the most recent row from `earnings_history` when multiple rows are present,
**So that** the `.iloc[-1]` selection logic is exercised and a regression that picks the wrong row is caught — while eliminating a test that adds no independent failure mode over the existing set-equality check.

### Scope In
- Remove `test_fundamentals_returns_exactly_five_keys` (its assertion is fully implied by `test_fundamentals_returns_correct_schema`)
- Add `test_fundamentals_eps_surprise_uses_most_recent_earnings_row`: mock `earnings_history` with two rows (older `epsDifference: 0.05`, newer `epsDifference: 0.20`), assert `result["eps_surprise"] == 0.20`

### Scope Out
- No changes to `get_fundamentals` implementation — the `.iloc[-1]` logic already exists
- No changes to any other test method
- No changes to `data/stock.py`

### Acceptance Criteria
- Given `earnings_history` contains two rows with `epsDifference` values `[0.05, 0.20]` (older first, newer last), when `get_fundamentals` is called, then `result["eps_surprise"]` equals `0.20` — not `0.05`
- Given `test_fundamentals_returns_exactly_five_keys` is removed, when the test suite runs, then `test_fundamentals_returns_correct_schema` continues to provide the key-set guarantee with no gap
- Given all remaining tests run, when the suite completes, then no regressions are introduced

### Definition of Done
- [ ] `test_fundamentals_returns_exactly_five_keys` removed
- [ ] `test_fundamentals_eps_surprise_uses_most_recent_earnings_row` added and passing
- [ ] All other tests continue to pass

---

## Story 3: Add numpy Scalar Type-Conversion Test for _safe_float

**As a** system (data pipeline quality gate),
**I want** a test that passes `numpy.float64` values as mock `Ticker.info` and `earnings_history` data to `get_fundamentals`,
**So that** the `_safe_float` helper's numpy-scalar unwrapping path is exercised and a regression that allows `numpy.float64` to leak into the return dict is caught.

### Scope In
- Add `import numpy as np` to `tests/test_stock.py`
- Add `numpy` as a pinned direct dependency in `requirements.txt`
- Add `test_fundamentals_numpy_scalar_values_are_converted_to_python_float`: mock all `Ticker.info` values and `epsDifference` as `numpy.float64`; assert `type(result["pe_ratio"]) is float` and `type(result["eps_surprise"]) is float`

### Scope Out
- No changes to `_safe_float` implementation — the `float()` cast already handles numpy scalars
- No additional numpy-type assertions for `get_stock_history` — that function uses pandas `.iterrows()` which already produces Python-native types via explicit `float()` / `int()` casts
- No changes to `data/stock.py`

### Acceptance Criteria
- Given `Ticker.info` returns `numpy.float64` values for all four mapped fields, when `get_fundamentals` is called, then each corresponding value in the returned dict is a bare Python `float` — `type(result["pe_ratio"]) is float` passes
- Given `earnings_history` contains a `numpy.float64` `epsDifference` value, when `get_fundamentals` is called, then `type(result["eps_surprise"]) is float` passes
- Given `numpy` is added to `requirements.txt`, when the test suite is installed and run in a clean environment, then the import resolves without error

### Definition of Done
- [ ] `import numpy as np` added to `tests/test_stock.py`
- [ ] `numpy==1.26.4` (or current stable) pinned in `requirements.txt`
- [ ] `test_fundamentals_numpy_scalar_values_are_converted_to_python_float` added and passing
- [ ] All existing tests continue to pass

---
