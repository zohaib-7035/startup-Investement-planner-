# Analysis: Generate Rule-Based Stock Recommendation
Date: 2026-07-01
Story: 2026-07-01-generate-stock-recommendation-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

This is a greenfield Python data-pipeline project with no web framework, ORM, or persistence layer. The module layout is `data/` for retrieval and transformation logic, `tests/` for all test files. Three modules now exist: `data/stock.py` (yfinance financial data retrieval via `get_stock_history` and `get_fundamentals`) and `data/sentiment.py` (LLM-based sentiment classification via `analyze_sentiment`). The established pattern across all three existing public functions is: stateless wrapper, exception boundary at the function level, fixed-schema return dict with Python-native types only, and module-level constants for fallback values. Dependencies are pinned at `yfinance==0.2.40`, `pandas==2.2.2`, `numpy==1.26.4`, `pytest==8.2.2`, `anthropic==0.40.0`. `generate_recommendation` introduces no new external dependencies — it is the first function in the pipeline implemented entirely in the Python standard library with no imports beyond `data/screener.py` itself.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `get_stock_history` | `data/stock.py` | Established exception-boundary + fixed-schema return pattern; defensive guards at entry (empty df, invalid ticker) |
| `get_fundamentals` | `data/stock.py` | Demonstrates multi-field None handling: `_safe_float` private helper normalises type-unsafe inputs from yfinance; returns `.copy()`-free fixed dict |
| `_safe_float` helper | `data/stock.py` | Private helper that converts any value to Python `float` or `None` — the model for the `_safe_rsi` helper that `generate_recommendation` will need |
| `analyze_sentiment` | `data/sentiment.py` | Demonstrates module-level constants for fallback dicts (`.copy()` on return to prevent caller mutation), pre-call input validation guard, private helper for complex logic, exception boundary |
| Module-level constant pattern | `data/sentiment.py` | `_EMPTY_INPUT_FALLBACK`, `_API_FAILURE_FALLBACK`, `_SENTIMENT_SCORE_MAP` — same pattern applies to `_CONFIDENCE_MAP` and `_INVALID_RSI_FALLBACK` in `data/screener.py` |
| `unittest.mock.patch` test convention | `tests/test_stock.py`, `tests/test_sentiment.py` | All external calls patched; `generate_recommendation` has no external calls — all tests exercise pure Python logic with no patching required |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `generate_recommendation` | Python function | Core deliverable — does not exist yet; to be placed in a new `data/screener.py` module |
| `data/screener.py` | New Python module | Separate file justified by distinct concern (rule-based decision engine vs. data retrieval vs. LLM classification); follows `data/sentiment.py` naming convention |
| `_safe_rsi` | Private helper in `data/screener.py` | Validates that RSI is a finite numeric value within 0–100; returns `None` for None, non-numeric, negative, or > 100 values; modelled on `_safe_float` in `data/stock.py` |
| `_CONFIDENCE_MAP` | Module-level constant in `data/screener.py` | Maps `"Buy" → 0.85`, `"Sell" → 0.75`, `"Hold" → 0.50`; ensures confidence/action consistency is enforced by lookup, not by repeated literals |
| `_INVALID_RSI_FALLBACK` | Module-level constant in `data/screener.py` | `{"action": "Hold", "confidence": 0.0, "reason": "RSI value is missing or invalid."}` — returned only when RSI cannot be validated |
| Ordered rule evaluator | Logic inside `generate_recommendation` | Evaluates rules top-to-bottom: Buy (RSI < 30 AND eps_surprise > 0) → Sell (RSI > 70) → Hold; first match wins |
| `tests/test_screener.py` | New test file | Unit tests for all rule paths and edge cases; no mocking required — pure Python function |

---

## Strategic Approach

Add `generate_recommendation` to a new `data/screener.py` module following the same stateless-function, exception-boundary, fixed-schema-return pattern established by `get_fundamentals` and `analyze_sentiment`, but simplified: no external library calls, no parsing, no LLM integration. The function validates the RSI input via a private `_safe_rsi` helper (returning the invalid-input fallback immediately on failure), then evaluates an ordered rule set using strict comparison operators (`<` and `>`, not `≤` or `≥`), and constructs the return dict using a `_CONFIDENCE_MAP` lookup to guarantee `action`/`confidence` consistency. The rule set is an ordered top-to-bottom evaluation where the first matching rule wins and exits — no rule accumulation or scoring. Tests exercise pure Python logic and require no mocking, making this the simplest and fastest test file in the project.

---

## Key Design Decisions

- **Place `generate_recommendation` in `data/screener.py`, not `data/stock.py` or `data/sentiment.py`** — the screener is a decision engine consuming signals, not a data retrieval or LLM module; co-locating it would couple unrelated concerns.
- **No new dependencies** — the rule logic is pure Python `if/elif/else`; no pandas, no numpy, no LLM SDK; `requirements.txt` is unchanged.
- **Derive `confidence` from `_CONFIDENCE_MAP[action]` rather than inline literals** — consistent with how `data/sentiment.py` derives `score` from `_SENTIMENT_SCORE_MAP`; prevents `action`/`confidence` divergence if the rule set is later extended.
- **Validate RSI as the sole required input** — `eps_surprise` and `pe_ratio` are optional; a None RSI is the only condition that returns confidence `0.0` and bypasses all rules; this is modelled on the `not news_text.strip()` guard in `analyze_sentiment`.
- **Use strict `<` and `>` comparisons, not `<=` or `>=`** — RSI of exactly 30 or exactly 70 is not a clear signal; boundary values fall through to Hold. Story acceptance criteria use strict inequalities; the implementation must match.
- **Rule priority conflict does not exist at runtime** — RSI cannot simultaneously be `< 30` and `> 70`, so Buy and Sell rules are mutually exclusive by definition; no priority tie-breaking logic is needed. The order of evaluation (Buy first, then Sell) is semantically irrelevant but is preserved for readability.
- **`pe_ratio` is accepted but not evaluated** — accepted in the function signature for forward-compatibility; silently ignored in this iteration; no validation required.
- **Return `.copy()` of constant fallback dicts** — consistent with `data/sentiment.py`; prevents callers from mutating the module-level constant.
- **New test file `tests/test_screener.py`** — mirrors the module; no mocking required since there are no external calls; tests run faster than any other file in the suite.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| RSI boundary values (exactly 30 or exactly 70) falling through to Hold when caller expects Buy or Sell | High | Implementation must use strict `<` and `>` — test both boundary values explicitly: `rsi=30` → Hold, `rsi=70` → Hold |
| `eps_surprise=0.0` exactly — not positive, Buy rule blocked | High | `eps_surprise > 0` must be a strict comparison; `0.0` must not trigger Buy; test this case explicitly |
| RSI is None, non-numeric (string), negative, or > 100 — must return invalid-input Hold, never raise | High | `_safe_rsi` must handle all of these; the story mandates `confidence: 0.0` for this case only — distinct from the normal Hold at `0.50` |
| RSI is a numpy scalar (e.g. `numpy.float64`) from upstream pandas pipeline | Medium | `_safe_rsi` should call `float(value)` to normalise, consistent with `_safe_float` in `data/stock.py` — avoids type leakage if RSI is computed from a DataFrame |
| `eps_surprise` is `0.0` when provided as `float` vs `numpy.float64` | Medium | `eps_surprise > 0` works correctly for both Python float and numpy scalar since `numpy.float64(0.0) > 0` evaluates to `False`; no special handling needed but worth noting |
| Sell rule fire-check when both `rsi > 70` AND `eps_surprise > 0` | Low | Not a bug — RSI > 70 means the stock is overbought; the Sell rule correctly fires regardless of positive EPS surprise; the rules are not symmetric; test this to confirm Sell overrides what might otherwise look like a partial Buy signal |
| Return dict mutated by caller | Low | Return `.copy()` of constant fallback dicts; construct a fresh dict for non-fallback results (Buy and Sell) — never return a direct reference to a module-level mutable constant |
| Future rule additions breaking existing tests | Low | Tests assert specific action/confidence pairs for specific inputs; adding a new rule changes which tests fire for boundary inputs; no risk in this iteration but the ordered-evaluation pattern must be preserved in future changes |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| `rsi=25, eps_surprise=0.05, pe_ratio=15` → Buy, confidence 0.85 | Needs work | Straightforward: RSI < 30 AND eps_surprise > 0 → Buy rule fires |
| `rsi=75, eps_surprise=0.05, pe_ratio=15` → Sell, confidence 0.75 | Needs work | RSI > 70 → Sell rule fires; eps_surprise value is irrelevant to Sell |
| `rsi=50, eps_surprise=0.05, pe_ratio=15` → Hold, confidence 0.50 | Needs work | Neither rule fires → Hold |
| `rsi=25, eps_surprise=None` → Hold, confidence 0.50 | Needs work | Buy rule requires eps_surprise > 0; None fails this condition; falls through to Hold |
| `rsi=25, eps_surprise=-0.10` → Hold, confidence 0.50 | Needs work | Negative eps_surprise fails `> 0` check; Buy rule blocked; falls through to Hold |
| `rsi=75, eps_surprise=None, pe_ratio=None` → Sell, confidence 0.75 | Needs work | Sell rule checks only RSI; None inputs for other fields are irrelevant |
| `rsi=None` → Hold, confidence 0.0 | Needs work | `_safe_rsi` returns None; invalid-input fallback returned immediately |
| Returned dict has exactly keys `action`, `confidence`, `reason` | Needs work | Explicit dict construction; no extra keys from rule metadata |
| `confidence` is always Python `float` in [0.0, 1.0] | Needs work | `_CONFIDENCE_MAP` values are Python float literals; `0.0` in invalid-input fallback is also float |
| `action` and `confidence` are always consistent | Needs work | Enforced by `_CONFIDENCE_MAP[action]` lookup — confidence is never set independently of action |

---

## Dependencies

- **`data/screener.py`** — new module; `generate_recommendation` is its sole public function; `_safe_rsi` is private
- **`tests/test_screener.py`** — new test file; no mocking; exercises all rule branches and edge cases
- **`data/stock.py`** — unaffected; `get_stock_history` and `get_fundamentals` continue unchanged; `_safe_float` is the model for `_safe_rsi`
- **`data/sentiment.py`** — unaffected; `analyze_sentiment` continues unchanged; module-level constant pattern is the model for `_CONFIDENCE_MAP` and `_INVALID_RSI_FALLBACK`
- **`requirements.txt`** — unaffected; no new dependencies
- **Downstream consumers (future)** — portfolio screening, alerting, and backtesting pipelines that will call `generate_recommendation` with signal dicts produced by `get_fundamentals` and external RSI calculators
