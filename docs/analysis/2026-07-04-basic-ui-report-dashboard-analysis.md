# Analysis: Basic UI Report Dashboard
Date: 2026-07-04
Story: 2026-07-04-basic-ui-report-dashboard-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with no web framework, no ORM, and no persistence. Twenty modules live under `data/`, each exposing one or two public functions following a strict module-per-concern pattern. Every public function has an outer `try/except Exception` boundary and returns Python-native types only. Tests use `unittest.TestCase` class groupings run via pytest 8.2.2. There is no separate frontend repo — HTML generation from Python string formatting is a natural fit within the existing `data/` module layout. No new packages are required; this module uses Python stdlib only.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| Module-per-concern pattern | `data/*.py` (20 modules) | One public function per module; `render_report` slots in as module 21 |
| `_EMPTY_RESULT` module-level constant | `data/profile_advisor.py`, `data/screener.py`, `data/meta_agent.py`, etc. | All pure-Python modules define a fallback at module level and return `.copy()` — report.py will use a string constant instead of a dict |
| `try/except Exception` outer boundary | All 20 `data/` modules | Universal pattern; `render_report` must follow it — catches malformed input that bypasses pre-flight guards |
| Private `_helper` prefix | `_safe_rsi`, `_safe_float`, `_build_reasoning`, `_validate_profile`, etc. | All private helpers are `_`-prefixed; new helpers `_safe_field`, `_format_confidence`, `_badge_colour`, `_render_allocation` follow this rule |
| `unittest.TestCase` test classes | `tests/test_screener.py`, `tests/test_profile_advisor.py`, `tests/test_graph_reasoning.py` | Pure-Python modules use no mocking; test classes group scenarios (`TestOutputSchema`, `TestHappyPath`, `TestPreflightGuard`) |
| `generate_recommendation` output shape | `data/screener.py` | Returns `{action, confidence, reason}` — this is what `technical_signals` likely contains when fed from the pipeline |
| `get_fundamentals` output shape | `data/stock.py` | Returns `{pe_ratio, eps, eps_surprise, market_cap, dividend_yield, beta}` — this is what `fundamentals` contains |
| `aggregate_signals` output shape | `data/meta_agent.py` | Returns `{final_action, confidence, reasoning, conflicts}` — relevant if `recommendation` field comes from meta-agent |
| `calculate_risk_metrics` output | `data/risk.py` | Returns `{risk_level, ...}` — source for `risk_level` field |
| `optimize_portfolio` output | `data/portfolio.py` | Returns `{weights, ...}` — `weights` dict is the source for `portfolio_allocation` |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `data/report.py` | New Python module | Does not exist; to be created following module-per-concern pattern |
| `render_report(data)` | Public function | Single public function; input is a flat dict with 9 well-defined keys; output is `str` (HTML) — unique in the codebase where all other public functions return `dict` |
| `_EMPTY_REPORT` | Module-level string constant | Fallback HTML string (not a dict); `str` is immutable so no `.copy()` — just return `_EMPTY_REPORT` directly |
| `_safe_field(value)` | Private helper | Normalises any scalar field to string; `None` → `"N/A"`, `float` → formatted string, `str` → pass-through |
| `_format_confidence(score)` | Private helper | `0.85` → `"85%"`; `None` or non-numeric → `"N/A"`; clamps display if value outside `[0.0, 1.0]` |
| `_badge_colour(recommendation)` | Private helper | Maps `"BUY"` → `#28a745` (green), `"SELL"` → `#dc3545` (red), `"HOLD"` → `#fd7e14` (amber), unknown → `#6c757d` (grey); normalises to uppercase before lookup |
| `_render_allocation(alloc)` | Private helper | Converts `{ticker: weight_float}` dict to an HTML `<ul>` with `ticker: 50.0%` per item; `None` or empty → `"N/A"` |
| `_render_dict_section(d)` | Private helper | Converts arbitrary nested dict (e.g. `fundamentals`, `technical_signals`) to a `<dl>` definition-list of key→value pairs; handles `None` values per entry as `"N/A"` |
| `tests/test_report.py` | New test file | Pure Python, no mocking; target: all tests Strong; suggested classes below |

---

## Strategic Approach

`render_report` is the simplest function in the pipeline: no I/O, no LLM, no external calls — pure string formatting. The recommended approach is an f-string HTML template assembled by composing the outputs of the five private helpers into one `<html>` document with an inline `<style>` block. Pre-flight validation runs first: `None` input or empty dict both return `_EMPTY_REPORT` before any template logic runs. The outer `try/except` catches any downstream failure (malformed nested dict, unexpected type). Because the return type is `str` rather than `dict`, this module is the only one in the codebase where the fallback constant is a string — this should be documented in the module's single docstring.

---

## Key Design Decisions

- **Return type is `str`, not `dict`** — all other 20 public functions return `dict`; `render_report` returns an HTML `str`. This is intentional: the function's sole purpose is presentation, not data. The docstring must note this explicitly so the deviation is not mistaken for a bug.
- **`_EMPTY_REPORT` is a string constant, not a dict** — no `.copy()` needed (strings are immutable). Return it directly in pre-flight and exception paths.
- **`recommendation` is normalised to uppercase before badge lookup** — pipeline outputs from `screener.py` produce title-case `"Buy"`, while `meta_agent.py` produces uppercase `"BUY"`. Normalising inside `_badge_colour` with `str(rec).upper()` handles both without requiring the caller to normalise first.
- **Nested dict fields (`technical_signals`, `fundamentals`) rendered via `_render_dict_section`** — these fields are complex dicts from upstream modules; rendering them as flat key→value definition lists is the MVP-correct choice without hardcoding field names.
- **No imports from other `data/` modules** — `render_report` takes a pre-assembled dict; it does not call `get_fundamentals` or `generate_recommendation` itself. This keeps the module dependency-free and testable without any mocking.
- **Inline `<style>` block only** — no `<link rel="stylesheet">`, no CDN URLs. The returned HTML string must be fully self-contained and renderable by saving to any `.html` file.
- **`confidence_score` display clamped to `[0.0, 1.0]`** — upstream modules can theoretically return out-of-range floats; clamp before multiplying by 100 to avoid displaying `"150%"`.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| `recommendation` arrives as title-case `"Buy"` from screener vs uppercase `"BUY"` from meta_agent | High | Normalise with `str(rec).upper()` inside `_badge_colour` — test both casings explicitly |
| `technical_signals` or `fundamentals` is a deeply nested dict (e.g. nested dict of dicts) | Medium | `_render_dict_section` should flatten only one level; deeper nesting renders the inner dict as a raw `str()` — acceptable for MVP |
| `confidence_score` outside `[0.0, 1.0]` (e.g. `1.5`) from a buggy upstream module | Medium | Clamp to `[0.0, 1.0]` before display; never raise on bad value |
| `portfolio_allocation` weights do not sum to 1.0 (floating point drift) | Low | Display as-is — no normalisation; just render each weight as `weight * 100:.1f%` |
| `timestamp` could be a `datetime` object or a formatted string | Low | Apply `str(value)` in `_safe_field` — renders both correctly without special-casing |
| Very long `company_name` overflows layout | Low | CSS `word-break: break-word` on the company header prevents layout breakage |
| All 9 keys absent from dict (caller passes `{"other_key": "value"}`) | Low | Pre-flight only checks `None` and `{}`; unknown keys silently render as "N/A" via `_safe_field(data.get("key"))` — do not raise |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Given a fully populated data dict, when `render_report(data)` called, then returns non-empty HTML string with all 9 field values | Needs work | Module does not exist yet; pattern is clear — assert `len(result) > 0` and that each field value appears in the HTML string |
| Given HTML string, when saved and opened in browser, then sections are distinct and readable | Needs work | Cannot be machine-tested; test can assert structural tags present (`<html`, `<head`, `<body`, `<style`) — manual browser check in DoD |
| Given None fields, when rendered, then those fields show "N/A" | Needs work | Test each of the 9 keys individually set to `None`; assert `"N/A"` in result |
| Given `None` or `{}` input, when called, then returns fallback HTML without raising | Needs work | Two pre-flight guard tests: `render_report(None)` and `render_report({})` — assert returns `str`, contains "No data available", does not raise |
| Given `confidence_score` 0.0–1.0, when rendered, then displayed as percentage | Needs work | Test `0.85 → "85%"`, `1.0 → "100%"`, `0.0 → "0%"`, `None → "N/A"` |
| Given `recommendation` BUY/SELL/HOLD, when rendered, then badge is green/red/amber | Needs work | Test that the correct CSS hex colour code appears in the HTML for each of the three values and for title-case variants |
| Given `portfolio_allocation` dict, when rendered, then each ticker and weight% listed | Needs work | Test `{"AAPL": 0.5, "MSFT": 0.3}` → both `"AAPL"` and `"50.0%"` appear in the HTML; test `None → "N/A"` |

---

## Suggested Test Classes for `tests/test_report.py`

| Class | Tests | Mocking |
|-------|-------|---------|
| `TestOutputSchema` | result is `str`, starts with HTML tag, contains `<html`, `<head`, `<body`, `<style` | None |
| `TestHappyPath` | all 9 field values appear in the HTML output | None |
| `TestConfidenceFormatting` | `0.85 → "85%"`, `1.0 → "100%"`, `0.0 → "0%"`, `None → "N/A"` | None |
| `TestRecommendationBadge` | BUY → green hex, SELL → red hex, HOLD → amber hex, lowercase `"buy"` → green hex, unknown → grey hex | None |
| `TestNoneFieldFallback` | each of the 9 keys set to `None` individually → `"N/A"` in output | None |
| `TestPortfolioAllocation` | dict renders tickers + percentages, `None` → `"N/A"`, `{}` → `"N/A"` | None |
| `TestPreflightGuard` | `None` input → fallback HTML no exception, `{}` → fallback HTML no exception, result contains "No data available" | None |

---

## Dependencies

- `data/report.py` has **no imports from other `data/` modules** — it receives a pre-assembled dict; callers (e.g. `parallel_runner.py` in a future integration story) are responsible for assembling the dict
- No new packages required — stdlib only (`html` module for escaping user-provided strings recommended as a security measure)
- `tests/test_report.py` imports `render_report` from `data.report` only
- No changes to any existing module required
