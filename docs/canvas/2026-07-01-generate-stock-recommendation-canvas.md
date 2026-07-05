# REASONS Canvas: Generate Rule-Based Stock Recommendation
Date: 2026-07-01
Analysis: 2026-07-01-generate-stock-recommendation-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The data pipeline has no decision layer. It can retrieve price history, fundamentals, and news sentiment, but has no function that translates those signals into a structured, machine-readable trade recommendation that downstream screening and alerting components can consume.

**Goal:** Implement `generate_recommendation(rsi, eps_surprise, pe_ratio)` in a new `data/screener.py` module that applies a fixed ordered rule set to the provided signals and returns a Python dict with exactly three keys: `action` (one of `"Buy"`, `"Hold"`, `"Sell"`), `confidence` (Python float), and `reason` (non-empty string). The function must be deterministic, require no external calls, and never raise an exception to the caller.

**Definition of Done:**
- [ ] Given `rsi=25`, `eps_surprise=0.05`, `pe_ratio=15`, when `generate_recommendation` is called, then the returned dict contains `"action": "Buy"`, `"confidence": 0.85`, and a non-empty `"reason"` string
- [ ] Given `rsi=75`, `eps_surprise=0.05`, `pe_ratio=15`, when called, then the returned dict contains `"action": "Sell"`, `"confidence": 0.75`, and a non-empty `"reason"` string
- [ ] Given `rsi=50`, `eps_surprise=0.05`, `pe_ratio=15`, when called, then the returned dict contains `"action": "Hold"`, `"confidence": 0.50`, and a non-empty `"reason"` string
- [ ] Given `rsi=25`, `eps_surprise=None`, when called, then the Buy rule cannot fire (EPS condition unsatisfied) and the result is `"Hold"`, `"confidence": 0.50`
- [ ] Given `rsi=25`, `eps_surprise=-0.10`, when called, then the Buy rule does not fire (EPS not positive) and the result is `"Hold"`, `"confidence": 0.50`
- [ ] Given `rsi=75`, `eps_surprise=None`, `pe_ratio=None`, when called, then the Sell rule fires on RSI alone and the result is `"action": "Sell"`, `"confidence": 0.75`
- [ ] Given `rsi=None`, when called, then the function returns `"Hold"`, `"confidence": 0.0`, and a reason describing the invalid RSI — no exception propagates
- [ ] Given `rsi=30` (boundary), when called, then the Buy rule does not fire (strict less-than) and the result is `"Hold"`
- [ ] Given `rsi=70` (boundary), when called, then the Sell rule does not fire (strict greater-than) and the result is `"Hold"`
- [ ] Given `eps_surprise=0.0` exactly and `rsi=25`, when called, then the Buy rule does not fire (strict greater-than zero) and the result is `"Hold"`
- [ ] Given `rsi > 70` AND `eps_surprise > 0`, when called, then the Sell rule fires — positive EPS surprise does not suppress a Sell signal
- [ ] Given any input, when called, then the returned dict contains exactly the keys `action`, `confidence`, and `reason`
- [ ] Given any input, when called, then `confidence` is always a Python `float`
- [ ] Given any input, when called, then `action` and `confidence` are always internally consistent — `"Buy"` always pairs with `0.85`, `"Sell"` with `0.75`, `"Hold"` with `0.50` or `0.0` (invalid RSI only)
- [ ] No new entries in `requirements.txt` — pure Python standard library only
- [ ] No regression in `get_stock_history`, `get_fundamentals`, or `analyze_sentiment` flows

---

## E — Entities

### Data Entities

| Entity | Type | Key Fields | Relationships |
|--------|------|-----------|---------------|
| `RecommendationRecord` | Return schema (dict) | `action` (str: `"Buy"` / `"Hold"` / `"Sell"`), `confidence` (float: `0.85` / `0.75` / `0.50` / `0.0`), `reason` (str: non-empty explanation of which rule fired) | Produced by `generate_recommendation`; consumed by portfolio screening, alerting, and backtesting modules |
| `_CONFIDENCE_MAP` | Module-level constant | Maps `"Buy" → 0.85`, `"Sell" → 0.75`, `"Hold" → 0.50`; enforces action/confidence consistency by lookup | Used inside `generate_recommendation` to construct the return dict; never accessed directly by callers |
| `_INVALID_RSI_FALLBACK` | Module-level constant | `{"action": "Hold", "confidence": 0.0, "reason": "RSI value is missing or invalid."}` | Returned only when `_safe_rsi` returns None; distinct from normal Hold at `0.50` |
| Rule set | Ordered evaluation logic inside `generate_recommendation` | Rule 1 (Buy): RSI < 30 AND eps_surprise > 0; Rule 2 (Sell): RSI > 70; Rule 3 (Hold): all other cases | First match wins; rules are mutually exclusive (RSI cannot be < 30 and > 70 simultaneously) |

No database schema, no migration, no external API. This is a stateless pure-Python decision function.

---

## A — Approach

**Pattern:** Stateless pure-Python rule engine — ordered if/elif/else evaluation with module-level constants for action/confidence lookup, a private RSI validation helper, and a fixed-schema return dict. No external dependencies, no LLM, no parsing.

**Strategy:** Validate the RSI input through `_safe_rsi` (returning the invalid-input fallback immediately on failure), then evaluate the rule set top-to-bottom using strict comparison operators, derive `confidence` from `_CONFIDENCE_MAP` using the matched action label, and construct a fresh three-key return dict. This is the simplest function in the pipeline: no external calls, no parsing, no mocking required in tests — all test scenarios are pure function inputs and outputs.

**Scope In:**
- Single-call rule evaluation against three signal inputs: `rsi`, `eps_surprise`, `pe_ratio`
- Fixed rule set: Buy (RSI < 30 AND eps_surprise > 0) → Sell (RSI > 70) → Hold
- Fixed confidence values: Buy = 0.85, Sell = 0.75, Hold = 0.50; invalid RSI = 0.0
- RSI validation via `_safe_rsi` — returns None for None, non-numeric, negative, or > 100
- `_safe_rsi` normalises numpy scalars by calling `float()`, consistent with `_safe_float` in `data/stock.py`
- `pe_ratio` accepted in signature but not evaluated — forward-compatibility only
- Three-key return dict: `action`, `confidence`, `reason`
- Unit tests for all rule paths, boundary values, and edge cases in `tests/test_screener.py`
- No changes to `requirements.txt`

**Scope Out:**
- No LLM call — rules are deterministic Python logic only
- No dynamic or caller-configurable rules
- No `pe_ratio` rule in this iteration
- No actions beyond the three agreed values (e.g. "Strong Buy", "Reduce")
- No portfolio-level aggregation
- No historical backtesting
- No fractional or dynamically computed confidence scores
- No retry, async, or streaming

---

## S — Structure

**Module:** `data/screener.py`

**New Files:**
- `data/screener.py` — `generate_recommendation` public function, `_safe_rsi` private helper, and module-level constants `_CONFIDENCE_MAP` and `_INVALID_RSI_FALLBACK`
- `tests/test_screener.py` — unit tests for `generate_recommendation`; no mocking required

**Modified Files:**
- None

**Database:**
- None

---

## O — Operations

1. Create `data/screener.py` with two module-level constants: `_CONFIDENCE_MAP` mapping each of the three action strings to its fixed confidence float, and `_INVALID_RSI_FALLBACK` dict returned when RSI validation fails — both constants must be defined before the functions that reference them

2. Add the `_safe_rsi(value)` private helper to `data/screener.py` — calls `float(value)` inside a try/except to normalise any numeric type including numpy scalars, then validates the result is a finite number in the range 0 to 100 inclusive (using `math.isfinite`), returns the normalised float on success or `None` on any failure; returns `None` for None input without attempting conversion

3. Add the `generate_recommendation(rsi, eps_surprise, pe_ratio)` public function to `data/screener.py` — first passes `rsi` through `_safe_rsi` and returns `_INVALID_RSI_FALLBACK.copy()` immediately if the result is `None`; then evaluates rules in order using strict comparisons: if `rsi < 30` AND `eps_surprise` is not None AND `eps_surprise > 0` then action is `"Buy"`, elif `rsi > 70` then action is `"Sell"`, else action is `"Hold"`; derives `confidence` from `_CONFIDENCE_MAP[action]`; returns a freshly constructed three-key dict with the action, confidence, and a plain-language reason describing which rule fired

4. Create `tests/test_screener.py` — no mocking required; write tests covering: Buy rule fires (`rsi=25, eps_surprise=0.05`), Sell rule fires (`rsi=75`), Hold (no rule, `rsi=50`), Buy blocked by None `eps_surprise`, Buy blocked by negative `eps_surprise`, Buy blocked by `eps_surprise=0.0` exactly (strict greater-than), Sell fires when `eps_surprise > 0` (positive EPS does not override overbought RSI), RSI boundary `rsi=30` → Hold, RSI boundary `rsi=70` → Hold, `rsi=None` → invalid-input Hold with confidence `0.0`, string RSI (`rsi="high"`) → invalid-input Hold, negative RSI → invalid-input Hold, RSI > 100 → invalid-input Hold, schema key count (exactly three keys), `confidence` is Python float, action/confidence consistency across all three action values

---

## N — Norms

### Python / Data Pipeline Norms

- Module layout: `data/` for retrieval and transformation logic; `tests/` for all test files; one module per concern — rule-engine logic in `data/screener.py`, financial data in `data/stock.py`, LLM logic in `data/sentiment.py`
- Functions are stateless — no side effects, no module-level mutable state (constants are immutable)
- All external exceptions are caught at the function boundary — since this function makes no external calls, only the `_safe_rsi` conversion step can raise and it is fully wrapped
- Return schema is a plain Python dict — no custom classes, no third-party types in the public return value
- All return values use Python-native types — `str` for `action` and `reason`, `float` for `confidence`
- The returned dict always has exactly the three contracted keys — callers must never need to guard against `KeyError`
- Private helpers are prefixed with `_` — not part of the public module API
- No new direct dependencies — pure Python standard library only; `requirements.txt` is unchanged
- Test file names mirror the module they test: `data/screener.py` → `tests/test_screener.py`
- Tests for this module require no mocking — all assertions are pure function input/output; do not introduce `unittest.mock.patch` where it is not needed

---

## S — Safeguards

### Data Pipeline Safeguards

- Never let an exception propagate past `generate_recommendation` — `_safe_rsi` must catch all conversion and validation errors; the outer function must never raise
- Never use `<=` or `>=` for RSI boundary comparisons — the story specifies strict `<` and `>` only; boundary values (exactly 30 and exactly 70) must fall through to Hold
- Never use `>=` or `==` for the `eps_surprise > 0` check — `eps_surprise=0.0` must not trigger Buy
- Never derive `confidence` inline as a magic literal — always look up from `_CONFIDENCE_MAP[action]` to guarantee action/confidence consistency
- Never return a direct reference to `_INVALID_RSI_FALLBACK` — always return `.copy()` to prevent caller mutation of the module-level constant
- Never evaluate `pe_ratio` in any rule condition — it is accepted in the signature for forward-compatibility only; any accidental evaluation would be a scope creep bug
- Always validate RSI before evaluating any rule — `_safe_rsi` must run first; do not pass a raw unvalidated RSI value into a comparison
- Always construct a fresh dict for non-fallback results (Buy, Sell, Hold) — do not reuse or mutate module-level constants for successful rule matches
- Do not modify `data/stock.py`, `data/sentiment.py`, or any existing test file as part of this story

---

## Change Log

[Appended by /prompt-update and /sync]
