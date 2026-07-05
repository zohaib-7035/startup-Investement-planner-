# User Story: Analyze Company News Sentiment via LLM
Date: 2026-06-30
Source: Pasted text

---

## Story 1: Classify News Excerpt Sentiment for a Named Company

**As a** system (financial data pipeline consumer),
**I want** a function `analyze_sentiment(news_text)` that classifies the sentiment of a news excerpt about a company using an LLM and returns a structured result with a sentiment label, numeric score, and plain-language reason,
**So that** downstream screening, alerting, and model-training components receive a consistently structured, machine-readable sentiment signal without needing to know the LLM provider or prompt internals.

### Scope In
- Accept `news_text` (string) as the sole parameter
- Call an LLM with a fixed financial-analyst system prompt and the provided news text
- Return a Python dict with exactly three keys: `sentiment` (string: `"Positive"`, `"Neutral"`, or `"Negative"`), `score` (int: `+1`, `0`, or `-1`), `reason` (string: plain-language explanation)
- `sentiment` and `score` are always consistent with each other: `"Positive"` maps to `+1`, `"Neutral"` to `0`, `"Negative"` to `-1`
- `reason` is a concise string (one to three sentences) explaining the classification
- Empty or whitespace-only `news_text` returns a `"Neutral"` / `0` result without calling the LLM
- LLM API failures, timeouts, or malformed responses return a neutral fallback dict with `reason` describing the failure — no raw exceptions propagate to the caller

### Scope Out
- No multi-excerpt batch processing in a single call — one news text per call
- No named-entity extraction or identification of which company is mentioned — caller is responsible for providing relevant text
- No caching of LLM responses
- No support for sentiment beyond the three agreed labels (e.g. "Very Positive", numeric fine-grained scores) — defer to a future story
- No streaming LLM responses — synchronous call only
- No retry logic for transient API failures — document as known limitation
- No model selection exposed to the caller — model is an internal implementation detail

### Acceptance Criteria
- Given a news text describing clearly positive company news (e.g. strong earnings, new product launch), when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Positive"`, `"score": 1`, and a non-empty `"reason"` string
- Given a news text describing clearly negative company news (e.g. earnings miss, product recall, legal trouble), when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Negative"`, `"score": -1`, and a non-empty `"reason"` string
- Given a news text that is factual and non-evaluative (e.g. a company changed its CEO without positive or negative framing), when `analyze_sentiment` is called, then the returned dict contains `"sentiment": "Neutral"`, `"score": 0`, and a non-empty `"reason"` string
- Given an empty string or whitespace-only input, when `analyze_sentiment` is called, then the function returns `{"sentiment": "Neutral", "score": 0, "reason": "No news text provided."}` without calling the LLM
- Given any input, when `analyze_sentiment` is called, then the returned dict contains exactly the keys `sentiment`, `score`, and `reason` — no extra keys are ever present
- Given any input, when called, then `score` is always the integer `+1`, `0`, or `-1` — never a string, float, or `None`
- Given an LLM API failure or a response that cannot be parsed into the agreed schema, when called, then the function returns `{"sentiment": "Neutral", "score": 0, "reason": "Sentiment analysis unavailable."}` — no exception propagates to the caller
- Given any valid input, when called, then `sentiment` and `score` are always internally consistent — `"Positive"` always pairs with `1`, `"Neutral"` with `0`, `"Negative"` with `-1`

### Definition of Done
- [ ] Implementation complete and peer-reviewed
- [ ] Unit tests written for: positive news, negative news, neutral news, empty input, LLM API exception, malformed LLM response — all LLM calls mocked
- [ ] Return schema validated (correct keys, correct types, sentiment/score consistency) in tests
- [ ] No regression in `get_stock_history` or `get_fundamentals` flows
- [ ] LLM provider and model pinned or documented in `requirements.txt` or a config file
- [ ] Product/requester has reviewed and confirmed the output structure matches downstream expectations
- [ ] QA sign-off complete

---
