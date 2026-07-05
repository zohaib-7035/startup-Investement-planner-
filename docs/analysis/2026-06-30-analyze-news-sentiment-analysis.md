# Analysis: Analyze Company News Sentiment via LLM
Date: 2026-06-30
Story: 2026-06-30-analyze-news-sentiment-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

This is a greenfield Python data-pipeline project with no web framework, ORM, or persistence layer. The module layout follows a two-package convention: `data/` for retrieval and transformation logic, `tests/` for all test files. Two functions exist: `get_stock_history` (yfinance OHLCV retrieval) and `get_fundamentals` (yfinance fundamentals retrieval), both in `data/stock.py`. The established pattern across both functions is: thin stateless wrapper over an external library, exception boundary at the function level, fixed-schema return dict with only Python-native types, and mock-based unit tests with no live network calls. Dependencies are pinned at `yfinance==0.2.40`, `pandas==2.2.2`, `numpy==1.26.4`, and `pytest==8.2.2`. There is no frontend stack. `analyze_sentiment` introduces the first LLM dependency into the project — a new category of external service distinct from the financial data APIs used so far.

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| `get_stock_history` function | `data/stock.py` | Established thin-wrapper pattern: exception boundary, fixed-schema dict, mock-based tests |
| `get_fundamentals` function | `data/stock.py` | Same pattern; demonstrates how to handle multiple failure modes (empty dict, missing fields, exceptions) |
| `_safe_float` helper | `data/stock.py` | Demonstrates private helper pattern for type normalisation — `analyze_sentiment` will need an analogous JSON-parsing helper |
| `unittest.mock.patch` test convention | `tests/test_stock.py` | All external calls patched; same approach applies to LLM API calls |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| `analyze_sentiment` function | Python function | Core deliverable — does not exist yet; to be placed in a new `data/sentiment.py` module to keep LLM logic separate from financial data retrieval |
| `data/sentiment.py` | New Python module | Separate file justified by different external dependency class (LLM API vs. financial data API); keeps `data/stock.py` stable |
| Financial-analyst system prompt | Module-level constant in `data/sentiment.py` | Fixed prompt string: "You are an AI financial analyst that reads news articles about companies and outputs sentiment." — must not be caller-configurable |
| LLM client initialisation | Logic inside `analyze_sentiment` | Instantiates the Anthropic client; API key read from environment variable `ANTHROPIC_API_KEY` — never hardcoded |
| JSON response parser | Private helper `_parse_llm_response` in `data/sentiment.py` | Extracts `sentiment`, `score`, `reason` from LLM text output; validates label is one of the three agreed values; returns `None` on any parse failure |
| Empty-input guard | Logic inside `analyze_sentiment` | Checks `not news_text.strip()` before making any API call; returns neutral fallback immediately |
| Neutral fallback dict | Constant or inline in `data/sentiment.py` | Returned on empty input, API failure, or unparseable response — always `{"sentiment": "Neutral", "score": 0, "reason": "..."}` |
| `anthropic` Python SDK | New dependency in `requirements.txt` | Provides `Anthropic` client and message API; must be pinned |
| Unit tests for `analyze_sentiment` | `tests/test_sentiment.py` | New test file mirroring `data/sentiment.py`; all LLM calls mocked; covers positive, negative, neutral, empty input, API exception, malformed response |

---

## Strategic Approach

Add `analyze_sentiment` to a new `data/sentiment.py` module — separate from `data/stock.py` — following the same thin-wrapper pattern already established but adapted for LLM output: call the Anthropic API with a fixed system prompt, parse the JSON response, validate the sentiment label, and construct the three-key return dict. The primary complexity over the existing functions is response parsing: unlike yfinance which returns a structured DataFrame, the LLM returns free text that must be parsed as JSON and validated before use. A private `_parse_llm_response` helper isolates this parsing logic and returns `None` on any failure, allowing `analyze_sentiment` to fall back to the neutral dict cleanly. The API key is read from the environment — never hardcoded — consistent with twelve-factor app principles. Tests mock the Anthropic client at the module boundary, identical in pattern to how yfinance is mocked.

---

## Key Design Decisions

- **Place `analyze_sentiment` in `data/sentiment.py`, not `data/stock.py`** — the LLM API is a fundamentally different external dependency class; co-locating it with financial data retrieval would couple unrelated concerns and make mocking harder in tests.
- **Use the Anthropic Python SDK with `claude-haiku-4-5-20251001`** — Haiku is the fastest and cheapest Claude model, appropriate for a short-text classification task; the model is an internal implementation detail and is not exposed to callers.
- **Instruct the LLM to respond in JSON only** — the system prompt and user message both explicitly request JSON output; `_parse_llm_response` uses `json.loads()` inside a try/except to handle any deviation from expected format.
- **Validate the sentiment label after parsing** — LLMs can hallucinate; after `json.loads()` succeeds, confirm `sentiment` is one of `"Positive"`, `"Neutral"`, `"Negative"` and `score` is one of `1`, `0`, `-1` before returning. A valid JSON response with an out-of-schema label is treated as a parse failure.
- **Derive `score` from `sentiment` rather than trusting the LLM's score field** — the LLM may return `score: "+1"` (string) or `score: 1.0` (float); rather than normalising unpredictable LLM output, map `sentiment` → `score` deterministically in `_parse_llm_response`.
- **Empty-input guard before API call** — avoids a billable LLM call for a trivially invalid input; consistent with the `df.empty` guard in `get_stock_history`.
- **New test file `tests/test_sentiment.py`** — mirrors the module being tested; keeps `tests/test_stock.py` focused on financial data retrieval.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| LLM returns valid JSON but with unexpected `sentiment` label (e.g. `"Mixed"`, `"Bullish"`) | High | `_parse_llm_response` must validate label is exactly one of the three agreed values; treat any other value as a parse failure and return neutral fallback |
| LLM wraps JSON in markdown code fences (e.g. ` ```json\n{...}\n``` `) | High | `json.loads()` will fail on raw markdown-wrapped output; `_parse_llm_response` must strip common markdown wrapping before parsing |
| `ANTHROPIC_API_KEY` not set in environment | High | `anthropic.Anthropic()` raises `anthropic.AuthenticationError` if key is absent; caught by outer try/except; returns neutral fallback with descriptive reason |
| LLM returns `score` as string `"+1"` or float `1.0` instead of int | Medium | Do not trust LLM's score field; derive `score` from validated `sentiment` label in `_parse_llm_response` |
| LLM `reason` field contains embedded quotes or newlines that break JSON | Medium | `json.loads()` handles this correctly if the LLM produces valid JSON; if not, `_parse_llm_response` returns `None` and the fallback is used |
| Anthropic API rate-limiting or network timeout | Medium | No retry in scope; caught by outer try/except; returns neutral fallback; document as known limitation |
| `ANTHROPIC_API_KEY` accidentally hardcoded in tests | Low | Tests must mock the client at `data.sentiment.anthropic.Anthropic` — never instantiate a real client in tests |
| Anthropic SDK version drift breaks message API | Low | Pin `anthropic` at a specific version in `requirements.txt`; test against that version only |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Positive news → `sentiment: "Positive"`, `score: 1`, non-empty `reason` | Needs work | No implementation; straightforward with LLM call + `_parse_llm_response` validation |
| Negative news → `sentiment: "Negative"`, `score: -1`, non-empty `reason` | Needs work | Same path as positive; different expected LLM output |
| Neutral news → `sentiment: "Neutral"`, `score: 0`, non-empty `reason` | Needs work | Same path; LLM must classify factual/non-evaluative text correctly |
| Empty/whitespace input → neutral fallback dict, no LLM call | Needs work | Simple `not news_text.strip()` guard before API call |
| Returned dict has exactly keys `sentiment`, `score`, `reason` | Needs work | Explicit dict construction in `_parse_llm_response` and fallback constant |
| `score` is always int `+1`, `0`, or `-1` | Needs work | Derive from validated `sentiment` label, not from LLM's raw score field |
| LLM API failure → neutral fallback dict, no exception propagates | Needs work | Outer try/except covers this; consistent with existing `get_fundamentals` pattern |
| `sentiment` and `score` always internally consistent | Needs work | Enforced by deterministic `sentiment → score` mapping in `_parse_llm_response` |

---

## Dependencies

- **`anthropic` Python SDK** — new direct dependency; provides `Anthropic` client, `messages.create()` API, and exception types (`AuthenticationError`, `APIError`); must be pinned in `requirements.txt`
- **`ANTHROPIC_API_KEY`** — environment variable; must be set in the runtime environment; not added to `requirements.txt`; should be documented in a `.env.example` or project README
- **`data/sentiment.py`** — new module; `analyze_sentiment` is its sole public function; `_parse_llm_response` is private
- **`tests/test_sentiment.py`** — new test file; mocks `data.sentiment.anthropic.Anthropic`; no changes to `tests/test_stock.py`
- **`data/stock.py`** — unaffected; `get_stock_history` and `get_fundamentals` continue unchanged
- **Downstream consumers (future)** — screening, alerting, and model-training pipelines (out of scope; `analyze_sentiment` is their input boundary)
