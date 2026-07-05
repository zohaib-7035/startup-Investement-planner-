# REASONS Canvas: Analyze Company News Sentiment via LLM
Date: 2026-06-30
Analysis: 2026-06-30-analyze-news-sentiment-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** No sentiment analysis capability exists in the data pipeline. Downstream screening, alerting, and model-training components have no structured, machine-readable signal for how a news excerpt is likely to be perceived by the market for a given company.

**Goal:** Implement `analyze_sentiment(news_text)` in a new `data/sentiment.py` module that calls the Anthropic Claude API with a fixed financial-analyst system prompt, parses and validates the JSON response, and returns a Python dict with exactly three keys: `sentiment` (one of `"Positive"`, `"Neutral"`, `"Negative"`), `score` (int `+1`, `0`, or `-1`), and `reason` (non-empty string). The function must never raise an exception to the caller.

**Definition of Done:**
- [ ] Given a news text describing clearly positive company news, when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Positive"`, `"score": 1`, and a non-empty `"reason"` string
- [ ] Given a news text describing clearly negative company news, when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Negative"`, `"score": -1`, and a non-empty `"reason"` string
- [ ] Given a news text that is factual and non-evaluative, when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Neutral"`, `"score": 0`, and a non-empty `"reason"` string
- [ ] Given an empty string or whitespace-only input, when called, then the function returns the neutral fallback dict without calling the LLM
- [ ] Given any input, when called, then the returned dict contains exactly the keys `sentiment`, `score`, and `reason` — no extra keys are ever present
- [ ] Given any input, when called, then `score` is always the integer `1`, `0`, or `-1` — never a string, float, or `None`
- [ ] Given an LLM API failure or a response that cannot be parsed into the agreed schema, when called, then the function returns the neutral fallback dict — no exception propagates to the caller
- [ ] Given any valid input, when called, then `sentiment` and `score` are always internally consistent — `"Positive"` always pairs with `1`, `"Neutral"` with `0`, `"Negative"` with `-1`
- [ ] Unit tests written and passing for: positive news, negative news, neutral news, empty input, LLM API exception, malformed JSON response, markdown-fenced JSON response — all LLM calls mocked
- [ ] `anthropic` SDK pinned in `requirements.txt`
- [ ] `ANTHROPIC_API_KEY` environment variable documented in `.env.example`
- [ ] No regression in `get_stock_history` or `get_fundamentals` flows

---

## E — Entities

### Data Entities

| Entity | Type | Key Fields | Relationships |
|--------|------|-----------|---------------|
| `SentimentRecord` | Return schema (dict) | `sentiment` (str: `"Positive"` / `"Neutral"` / `"Negative"`), `score` (int: `1` / `0` / `-1`), `reason` (str: non-empty explanation) | Produced by `analyze_sentiment`; consumed by screening, alerting, and model-training modules |
| `SENTIMENT_SCORE_MAP` | Module-level constant | Maps `"Positive" → 1`, `"Neutral" → 0`, `"Negative" → -1` | Used by `_parse_llm_response` to derive `score` deterministically from validated `sentiment` label |
| `SYSTEM_PROMPT` | Module-level constant | Fixed string: "You are an AI financial analyst that reads news articles about companies and outputs sentiment." | Passed as system role message on every Anthropic API call; not caller-configurable |
| `NEUTRAL_FALLBACK` | Module-level constant | `{"sentiment": "Neutral", "score": 0, "reason": "..."}` | Returned on empty input, API failure, or unparseable response |
| `anthropic.Anthropic` | External library client | Wraps the Anthropic API; exposes `messages.create()` | Instantiated inside `analyze_sentiment`; API key read from `ANTHROPIC_API_KEY` environment variable |

No database schema or migration is involved — this is a stateless LLM-calling function with no persistence layer.

---

## A — Approach

**Pattern:** Thin stateless wrapper over an external LLM API, with pre-call input validation, post-call JSON parsing and schema validation, and a deterministic score derivation step — following the same exception-boundary and fixed-schema-return pattern established by `get_stock_history` and `get_fundamentals`.

**Strategy:** Call `anthropic.Anthropic().messages.create()` with the fixed system prompt and the news text, extract the text content from the response, strip any markdown code fence wrapping the LLM may have added, parse as JSON, validate that `sentiment` is one of the three agreed labels, derive `score` deterministically from the validated label (never from the LLM's raw score field), and return the three-key dict. A private `_parse_llm_response` helper owns all parsing and validation logic and returns `None` on any failure; `analyze_sentiment` treats a `None` result identically to an API exception — returning the neutral fallback dict. The empty-input guard fires before any API call is made to avoid a billable request for trivially invalid input.

**Scope In:**
- Single news text input; one LLM call per invocation
- Fixed system prompt — not caller-configurable
- Three-key return dict: `sentiment`, `score`, `reason`
- Empty/whitespace-only input guard — returns neutral fallback without calling LLM
- Markdown code fence stripping in `_parse_llm_response`
- Sentiment label validation — any out-of-schema label treated as parse failure
- Deterministic `score` derived from validated `sentiment` label
- Neutral fallback on all failure modes (empty input, API error, parse failure)
- Anthropic SDK pinned in `requirements.txt`; `ANTHROPIC_API_KEY` documented in `.env.example`
- Unit tests for all acceptance criteria scenarios in `tests/test_sentiment.py`

**Scope Out:**
- Batch processing of multiple news texts in a single call
- Named-entity extraction or company identification
- Model selection exposed to the caller
- Caching of LLM responses
- Retry logic for transient API failures
- Sentiment labels beyond the three agreed values
- Streaming LLM responses
- OpenBB or any provider other than Anthropic in this iteration

---

## S — Structure

**Module:** `data/sentiment.py`

**New Files:**
- `data/sentiment.py` — `analyze_sentiment` public function and `_parse_llm_response` private helper; module-level constants for system prompt, score map, and neutral fallback
- `tests/test_sentiment.py` — unit tests for `analyze_sentiment`; all Anthropic client calls mocked via `unittest.mock.patch`
- `.env.example` — documents `ANTHROPIC_API_KEY=your_key_here`; no secrets committed

**Modified Files:**
- `requirements.txt` — `anthropic` SDK added at pinned version

**Database:**
- None

---

## O — Operations

1. Pin `anthropic` SDK in `requirements.txt` and create `.env.example` with `ANTHROPIC_API_KEY=your_key_here` — establishes the new dependency and documents the required environment variable before any module imports it

2. Create `data/sentiment.py` with three module-level constants: the fixed financial-analyst system prompt string, the `SENTIMENT_SCORE_MAP` dict mapping each of the three labels to its integer score, and the `NEUTRAL_FALLBACK` dict used as the return value on all failure paths

3. Add the `_parse_llm_response(text)` private helper to `data/sentiment.py` — strips markdown code fence wrapping if present (remove leading ` ```json ` or ` ``` ` lines and trailing ` ``` `), calls `json.loads()` inside a try/except, validates that the parsed `sentiment` key is present and is one of the three agreed labels, validates that `reason` is a non-empty string, derives `score` from `SENTIMENT_SCORE_MAP` using the validated `sentiment` label (ignores any `score` field the LLM returned), returns a clean three-key dict on success or `None` on any failure

4. Add the `analyze_sentiment(news_text)` public function to `data/sentiment.py` — first checks `not news_text.strip()` and returns the neutral fallback with reason `"No news text provided."` without calling the LLM; then wraps the entire Anthropic API call in a try/except: instantiates `anthropic.Anthropic()`, calls `messages.create()` with the system prompt and news text as user message requesting JSON output, passes the response text to `_parse_llm_response`, returns the parsed result if not `None`, otherwise returns the neutral fallback with reason `"Sentiment analysis unavailable."`; the outer except catches all exceptions and returns the neutral fallback

5. Create `tests/test_sentiment.py` — mock `data.sentiment.anthropic.Anthropic` at the class level for all tests; write tests covering: positive news LLM response (assert `sentiment == "Positive"`, `score == 1`, `reason` non-empty and is `str`), negative news LLM response (assert `sentiment == "Negative"`, `score == -1`), neutral news LLM response (assert `sentiment == "Neutral"`, `score == 0`), empty string input (assert neutral fallback, assert LLM client was never called), whitespace-only input (assert neutral fallback, assert LLM client never called), LLM API exception (assert neutral fallback returned, no exception propagates), malformed JSON response (assert neutral fallback), markdown-fenced JSON response (assert correct parsing — `sentiment` and `score` extracted correctly despite fences), out-of-schema sentiment label from LLM (assert neutral fallback), schema key count (assert `len(result) == 3` and `set(result.keys()) == {"sentiment", "score", "reason"}`), score is always Python int not string or float

---

## N — Norms

### Python / Data Pipeline Norms

- Module layout: `data/` for retrieval and transformation logic; `tests/` for all test files; one module per external dependency class — LLM logic in `data/sentiment.py`, financial data in `data/stock.py`
- Functions are stateless — no side effects, no module-level mutable state (constants are immutable)
- All external API exceptions are caught at the function boundary — raw third-party exceptions must never propagate to callers
- Return schema is a plain Python dict — no custom classes, no third-party types in the public return value
- All return values use Python-native types — `str` for `sentiment` and `reason`, `int` for `score`
- The returned dict always has exactly the three contracted keys — callers must never need to guard against `KeyError`
- Private helpers are prefixed with `_` — not part of the public module API
- Pin all direct dependencies in `requirements.txt` with exact versions
- Never hardcode API keys or secrets — read from environment variables only
- Test file names mirror the module they test: `data/sentiment.py` → `tests/test_sentiment.py`
- Tests must not make real LLM API calls — mock `anthropic.Anthropic` at the module boundary
- Do not add comments explaining what the code does — only add a comment when the WHY is non-obvious (e.g. the markdown fence stripping explains why stripping is needed)

---

## S — Safeguards

### Data Pipeline Safeguards

- Never let a raw Anthropic API exception propagate past `analyze_sentiment` — the function is the exception boundary
- Never hardcode `ANTHROPIC_API_KEY` in source code or test files — always read from environment; tests must mock the client, never instantiate a real one
- Never trust the LLM's `score` field — always derive `score` from the validated `sentiment` label using `SENTIMENT_SCORE_MAP`; LLM score output may be a string, float, or wrong value
- Always strip markdown code fence wrapping before calling `json.loads()` — Claude and other LLMs frequently wrap JSON output in ` ```json ``` ` blocks; `json.loads()` will raise on raw markdown
- Always validate `sentiment` is exactly one of the three agreed labels after parsing — treat any other value (e.g. `"Mixed"`, `"Bullish"`, `"Very Positive"`) as a parse failure and return the neutral fallback
- Always check for empty or whitespace-only input before making an API call — avoids a billable LLM request for trivially invalid input
- Never return a dict with fewer or more than the three agreed keys — construct the return dict explicitly; do not spread or unpack the raw JSON dict from the LLM
- Always return a non-empty string for `reason` — if the LLM returns an empty `reason`, treat it as a parse failure
- Do not modify `data/stock.py` or `tests/test_stock.py` as part of this story

---

## Change Log

[Appended by /prompt-update and /sync]
