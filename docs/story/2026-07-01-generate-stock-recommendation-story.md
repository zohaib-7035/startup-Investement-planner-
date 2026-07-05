# User Story: Generate Rule-Based Stock Recommendation
Date: 2026-07-01
Source: Pasted text

---

## Story 1: Apply Quantitative Rules to Generate a Buy/Hold/Sell Recommendation

**As a** system (financial data pipeline consumer),
**I want** a function `generate_recommendation(rsi, eps_surprise, pe_ratio)` that applies a fixed set of quantitative rules to market signals and returns a structured recommendation with an action, confidence score, and plain-language reason,
**So that** downstream portfolio screening, alerting, and strategy backtesting components receive a consistent, deterministic, machine-readable trade recommendation without needing to know the rule logic or its implementation.

### Scope In
- Accept three named parameters: `rsi` (float), `eps_surprise` (float or None), `pe_ratio` (float or None)
- Apply a fixed, ordered rule set implemented in pure Python — no LLM call required
- Rule set (evaluated top-to-bottom, first match wins):
  - **Buy** if `rsi < 30` AND `eps_surprise` is not None AND `eps_surprise > 0`
  - **Sell** if `rsi > 70`
  - **Hold** in all other cases
- Return a Python dict with exactly three keys: `action` (string: `"Buy"`, `"Hold"`, or `"Sell"`), `confidence` (float between 0.0 and 1.0 inclusive), and `reason` (string: plain-language explanation of which rule fired)
- Confidence values are fixed per action outcome, not dynamically computed:
  - `"Buy"` → `0.85` (RSI oversold with positive EPS surprise is a high-conviction signal)
  - `"Sell"` → `0.75` (RSI overbought is a reliable but standalone signal)
  - `"Hold"` → `0.50` (no rule fired; neutral conviction)
- `rsi` is required; if it is None or not a valid number, return a Hold with `confidence 0.0` and reason describing the invalid input — no exception propagates
- `eps_surprise` and `pe_ratio` are optional (may be None); a None `eps_surprise` means the Buy rule's EPS condition cannot be satisfied, falling through to the next rule
- `pe_ratio` is accepted as a parameter for forward-compatibility but is not used in the current rule set — its presence or absence does not affect the output
- Place the function in a new `data/screener.py` module to keep rule logic separate from data retrieval and LLM logic
- Unit tests in `tests/test_screener.py` covering all rule paths and edge cases — no external calls to mock

### Scope Out
- No LLM call — rules are deterministic Python `if/elif/else` logic only
- No dynamic rule configuration or caller-supplied rules — rule set is fixed in the module
- No support for actions beyond the three agreed values (e.g. "Strong Buy", "Reduce") — defer to a future story
- No portfolio-level aggregation — function operates on a single stock's signals per call
- No historical backtesting — function applies rules to the current snapshot of signals only
- No pe_ratio rule in this iteration — `pe_ratio` is accepted but not evaluated
- No fractional or continuous confidence scores beyond the three fixed values — defer to a future story
- No streaming or async execution
- No caching of results

### Acceptance Criteria
- Given `rsi=25`, `eps_surprise=0.05`, `pe_ratio=15`, when `generate_recommendation` is called, then the returned dict contains `"action": "Buy"`, `"confidence": 0.85`, and a non-empty `"reason"` string
- Given `rsi=75`, `eps_surprise=0.05`, `pe_ratio=15`, when called, then the returned dict contains `"action": "Sell"`, `"confidence": 0.75`, and a non-empty `"reason"` string
- Given `rsi=50`, `eps_surprise=0.05`, `pe_ratio=15`, when called, then the returned dict contains `"action": "Hold"`, `"confidence": 0.50`, and a non-empty `"reason"` string
- Given `rsi=25`, `eps_surprise=None`, `pe_ratio=15`, when called, then the EPS condition cannot be satisfied and the Buy rule does not fire — result is `"Hold"` with `confidence 0.50`
- Given `rsi=25`, `eps_surprise=-0.10`, `pe_ratio=15`, when called, then the EPS surprise is negative, the Buy rule does not fire, and the result is `"Hold"` with `confidence 0.50`
- Given `rsi=75`, `eps_surprise=None`, `pe_ratio=None`, when called, then the Sell rule fires and the result is `"action": "Sell"`, `"confidence": 0.75`
- Given `rsi=None`, `eps_surprise=0.05`, `pe_ratio=15`, when called, then the function returns `"Hold"`, `confidence 0.0`, and a reason describing the invalid RSI — no exception propagates
- Given any input, when called, then the returned dict contains exactly the keys `action`, `confidence`, and `reason` — no extra keys
- Given any input, when called, then `confidence` is always a Python `float` between `0.0` and `1.0` inclusive
- Given any input, when called, then `action` and `confidence` are always internally consistent — `"Buy"` always pairs with `0.85`, `"Sell"` with `0.75`, `"Hold"` with `0.50` or `0.0` (invalid input only)

### Definition of Done
- [ ] Implementation complete and peer-reviewed
- [ ] Unit tests written for: Buy rule fires, Sell rule fires, Hold (no rule), Buy rule blocked by None eps_surprise, Buy rule blocked by negative eps_surprise, Sell fires when eps_surprise also present (RSI takes priority over Buy check), None rsi returns invalid-input Hold, schema key count correct, confidence is Python float, action/confidence consistency
- [ ] Return schema validated (correct keys, correct types, action/confidence consistency) in tests
- [ ] No regression in `get_stock_history`, `get_fundamentals`, or `analyze_sentiment` flows
- [ ] No new entries in `requirements.txt` — pure Python standard library only
- [ ] Product/requester has reviewed and confirmed the rule set and confidence values match downstream expectations
- [ ] QA sign-off complete

---
