# REASONS Canvas: Parallel Execution Runner
Date: 2026-07-03
Analysis: 2026-07-03-parallel-execution-runner-analysis.md
Scope: BE-only

---

## R — Requirements

**Problem:** The pipeline generates stock signals one agent at a time — each blocking the next. When six independent agents all require network I/O (yfinance, Anthropic), running them serially wastes wall-clock time proportional to the number of agents. There is also no protection against a single slow or failing agent blocking or crashing the full pipeline.

**Goal:** Add `run_agents_parallel` in a new `data/parallel_runner.py` module that executes all six analysis agents concurrently, enforces per-agent timeout and retry limits, and passes the aggregated results into the existing `aggregate_signals` function, returning the same 4-key decision dict.

**Definition of Done:**
- [ ] Given a valid ticker, start, and end with all agent data available, when called, then a 4-key dict is returned with final_action one of BUY/SELL/HOLD, confidence a float in zero to one, reasoning a non-empty string, and conflicts a list
- [ ] Given all six agents complete within the timeout, when called, then all six results are used in the aggregation and no agent is silently skipped
- [ ] Given one agent raises an exception on every attempt up to max_retries, when called, then that agent's fallback is used and the other five agents' results are applied normally; the function returns without raising
- [ ] Given one agent times out on every attempt up to max_retries, when called, then that agent's fallback is used and the other five results are applied normally; the function returns without raising
- [ ] Given all six agents fail on all retries, when called, then all fallbacks are used, aggregate_signals still receives a valid agent_outputs dict, and the function returns without raising
- [ ] Given news_texts is None, when called, then the news agent is invoked and its output is passed to the sentiment agent; no exception is raised regardless of news agent outcome
- [ ] Given news_texts is provided as a non-empty string, when called, then the news agent is NOT invoked and the provided value is passed directly to the sentiment agent
- [ ] Given timeout_seconds is zero or negative, when called, then it returns the empty result constant immediately without spawning any futures
- [ ] Given max_retries is zero, when called, then each agent is attempted exactly once with no retry
- [ ] Given any unhandled exception in the orchestrator itself, when called, then it returns the empty result constant and never raises

---

## E — Entities

### Data Contracts

| Name | Kind | Shape | Notes |
|------|------|-------|-------|
| `run_agents_parallel` return | dict | `{final_action (str), confidence (float), reasoning (str), conflicts (list)}` | Same shape as `aggregate_signals` return; `confidence` in [0.0, 1.0] |
| `_EMPTY_RESULT` | module constant | `{final_action: "HOLD", confidence: 0.0, reasoning: "", conflicts: []}` | Mirrors `meta_agent._EMPTY_RESULT`; returned on any orchestrator-level failure |
| Voting agent output shape | dict | `{action (str uppercase), confidence (float)}` | Required by `aggregate_signals` for keys technical, fundamentals, sentiment, macro |
| Risk agent output shape | dict | `{level (str)}` | Required by `aggregate_signals` under `agent_outputs["risk"]`; key is `level` not `risk_level` |
| News agent output shape | str | plain text string | Not a voting agent; output is the text input for `_run_sentiment_agent`; empty string is safe |
| `_SCORE_TO_ACTION` | module constant | `{1: "BUY", 0: "HOLD", -1: "SELL"}` | Maps `analyze_sentiment` score integer to uppercase action string |
| `_SENTIMENT_CONFIDENCE` | module constant | `{"Positive": 0.75, "Neutral": 0.50, "Negative": 0.75}` | Maps sentiment string to confidence float for the sentiment voter |

### Dependencies on Existing Modules

| Module | Function Consumed | Output Shape Received | Translation Required |
|--------|-------------------|-----------------------|---------------------|
| `data/stock.py` | `get_stock_history` | `list[dict]` with date, open, high, low, close, volume | Close prices extracted for RSI; full list passed to risk agent |
| `data/stock.py` | `get_fundamentals` | `{pe_ratio, pb_ratio, debt_to_equity, eps_last, eps_surprise}` | eps_surprise and pe_ratio extracted; action derived by wrapper |
| `data/screener.py` | `generate_recommendation` | `{action (title-case), confidence, reason}` | action must be uppercased; reason discarded |
| `data/sentiment.py` | `analyze_sentiment` | `{sentiment, score, reason}` | score mapped to action via `_SCORE_TO_ACTION`; sentiment mapped to confidence via `_SENTIMENT_CONFIDENCE` |
| `data/risk.py` | `calculate_risk_metrics` | `{var_1w_95, cvar_1w_95, portfolio_volatility, concentration_risk, risk_level, warnings}` | `risk_level` extracted and returned under key `level` |
| `data/meta_agent.py` | `aggregate_signals` | receives assembled `agent_outputs`; returns 4-key decision dict | None — this is the final call; output returned directly |

---

## A — Approach

**Pattern:** Concurrent coordinator — single public function, six private agent wrappers, one RSI helper, parallel submit-collect-retry loop using `ThreadPoolExecutor`.

**Strategy:** `run_agents_parallel` acts as a thin orchestrator that determines the effective news text, submits all five voting and risk agents to a `ThreadPoolExecutor` simultaneously, waits for each future with a per-call timeout, retries failed agents in subsequent rounds up to `max_retries`, applies per-agent fallback constants for any that never succeed, assembles the `agent_outputs` dict, and delegates to `aggregate_signals`. All shape translation happens inside the individual wrappers so the orchestrator handles only scheduling and assembly. The two-phase design — news determination first, five main agents second — keeps the dependency between news and sentiment explicit without requiring asyncio or inter-future communication.

**Scope In:**
- Single-ticker, single-call orchestration of six agents
- `ThreadPoolExecutor` with `max_workers=6` — one slot per main agent
- Per-agent fallback constants — one per agent, typed to the correct output shape
- RSI computation inline in the technical agent wrapper using numpy close prices
- Title-case-to-uppercase normalisation in the technical agent wrapper
- Score-to-action and sentiment-to-confidence mapping in the sentiment agent wrapper
- `risk_level` to `level` remapping in the risk agent wrapper
- `news_texts` short-circuit: skip news agent when caller provides text
- `max_retries=0` means exactly one attempt; loop uses `range(max_retries + 1)`

**Scope Out:**
- Asyncio or `async/await` — all downstream functions are synchronous
- Modifying any existing `data/` module — this story adds a new coordinator only
- Real news API integration — news agent stub returns empty string
- Real macro data integration — macro agent stub returns HOLD/0.0
- Multi-ticker batch execution
- Caching or persisting agent results across calls
- Streaming or partial result delivery before all agents finish
- UI, REST API, or CLI entrypoint

---

## S — Structure

**Module path:** `Z:\claude\stock_analyzer\data\parallel_runner.py`

**New Files:**
- `data/parallel_runner.py` — concurrency coordinator: module constants, RSI helper, six agent wrappers, public orchestrator
- `tests/test_parallel_runner.py` — full test suite; all downstream functions mocked via patch

**Modified Files:**
- None — no existing module is changed

**New Dependencies:**
- `concurrent.futures` — Python 3.9 stdlib; first use in this codebase; no install required

---

## O — Operations

1. Create `data/parallel_runner.py` with all module-level constants: `_EMPTY_RESULT` as a dict with keys final_action set to "HOLD", confidence set to 0.0, reasoning set to empty string, and conflicts set to empty list; `_TECHNICAL_FALLBACK`, `_FUNDAMENTALS_FALLBACK`, `_SENTIMENT_FALLBACK`, and `_MACRO_FALLBACK` each as a dict with action "HOLD" and confidence 0.0; `_RISK_FALLBACK` as a dict with key level set to "LOW"; `_NEWS_FALLBACK` as an empty string; `_SCORE_TO_ACTION` as a dict mapping integer 1 to "BUY", integer 0 to "HOLD", and integer negative-one to "SELL"; `_SENTIMENT_CONFIDENCE` as a dict mapping "Positive" to 0.75, "Neutral" to 0.50, and "Negative" to 0.75; add the import line for `concurrent.futures` and imports for all five downstream functions: `get_stock_history` and `get_fundamentals` from `data.stock`, `generate_recommendation` from `data.screener`, `analyze_sentiment` from `data.sentiment`, `calculate_risk_metrics` from `data.risk`, and `aggregate_signals` from `data.meta_agent`; also import `numpy` as `np`

2. Implement `_compute_rsi(close_prices, period=14)` — accepts a list of float close prices; returns `float` or `None`; validates that the list has more than `period` elements and returns `None` if not; uses numpy to compute price deltas from consecutive closes; separates deltas into gains (max with zero) and losses (max of negative delta with zero as absolute value); computes the initial average gain and average loss over the first `period` elements using a simple mean; then applies Wilder's smoothing for each remaining close price: `avg_gain = (avg_gain * (period - 1) + gain) / period` and the same for avg_loss; after the smoothing loop, if avg_loss is zero, return 100.0 (all gains); otherwise compute RS as avg_gain divided by avg_loss and RSI as 100 minus 100 divided by 1 plus RS; return `float(rsi)`; wrap the entire body in a try-except Exception that returns `None`

3. Implement `_run_news_agent(ticker)` as a stub — accepts ticker string; returns `_NEWS_FALLBACK` which is an empty string; wraps body in try-except Exception returning `_NEWS_FALLBACK`; and implement `_run_macro_agent(ticker)` as a stub — accepts ticker string; returns `_MACRO_FALLBACK.copy()`; wraps body in try-except Exception returning `_MACRO_FALLBACK.copy()`

4. Implement `_run_technical_agent(ticker, start, end)` — calls `get_stock_history(ticker, start, end)` to get history; if history is empty, returns `_TECHNICAL_FALLBACK.copy()`; extracts close prices as a list of floats from the history; calls `_compute_rsi(close_prices)` to get rsi which may be None; calls `get_fundamentals(ticker)` to get fundamentals dict; extracts `eps_surprise` and `pe_ratio` from fundamentals using `.get`; calls `generate_recommendation(rsi, eps_surprise, pe_ratio)` to get recommendation dict; extracts action from the recommendation and normalises it to uppercase via `str(result.get("action", "HOLD")).upper()`; extracts confidence as `float(result.get("confidence", 0.0))`; returns a dict with those two keys; wraps the entire body in try-except Exception that returns `_TECHNICAL_FALLBACK.copy()`

5. Implement `_run_fundamentals_agent(ticker)` — calls `get_fundamentals(ticker)`; extracts `eps_surprise` from the result; if `eps_surprise` is not None and its float value is strictly greater than zero, action is "BUY"; if `eps_surprise` is not None and its float value is strictly less than zero, action is "SELL"; otherwise action is "HOLD"; confidence is 0.70 when `eps_surprise` is not None and is a number, or 0.0 otherwise; returns dict with action and confidence wrapped in `float()`; wraps entire body in try-except Exception returning `_FUNDAMENTALS_FALLBACK.copy()`

6. Implement `_run_sentiment_agent(news_texts)` — if `news_texts` is falsy or `news_texts.strip()` is empty, returns `_SENTIMENT_FALLBACK.copy()`; calls `analyze_sentiment(news_texts)`; extracts `score` from the result defaulting to 0; extracts `sentiment` from the result defaulting to "Neutral"; maps score to action using `_SCORE_TO_ACTION.get(score, "HOLD")`; maps sentiment to confidence using `_SENTIMENT_CONFIDENCE.get(sentiment, 0.50)`; returns dict with action and `float(confidence)`; wraps entire body in try-except Exception returning `_SENTIMENT_FALLBACK.copy()`

7. Implement `_run_risk_agent(ticker, start, end)` — calls `get_stock_history(ticker, start, end)`; if history is empty, returns `_RISK_FALLBACK.copy()`; calls `calculate_risk_metrics(weights={ticker: 1.0}, returns_data={ticker: history})`; extracts `risk_level` from the metrics dict using `.get("risk_level")`; returns `{"level": risk_level or "LOW"}` — if `risk_level` is None, fall back to "LOW" so aggregate_signals applies no penalty; wraps entire body in try-except Exception returning `_RISK_FALLBACK.copy()`

8. Implement `run_agents_parallel(ticker, start, end, news_texts=None, timeout_seconds=30, max_retries=2)` — wrap the entire function body in a single outer try-except Exception that returns `_EMPTY_RESULT.copy()`; at the top, pre-flight check: if `timeout_seconds` is not a number or its float value is less than or equal to zero, return `_EMPTY_RESULT.copy()` immediately; then determine `effective_news`: if `news_texts is not None`, set `effective_news = news_texts`; otherwise create a single-worker `ThreadPoolExecutor`, submit `_run_news_agent(ticker)`, call `future.result(timeout=timeout_seconds)`, catch TimeoutError and Exception, use `_NEWS_FALLBACK` on any failure, and shut down that executor; define the five main agents as a dict named `agent_dispatch` mapping each agent name string to a two-element tuple of the callable and its argument list: "technical" maps to `(_run_technical_agent, [ticker, start, end])`, "fundamentals" maps to `(_run_fundamentals_agent, [ticker])`, "sentiment" maps to `(_run_sentiment_agent, [effective_news])`, "macro" maps to `(_run_macro_agent, [ticker])`, and "risk" maps to `(_run_risk_agent, [ticker, start, end])`; define `_fallbacks` as a dict mapping each name to its fallback constant; create a `ThreadPoolExecutor(max_workers=6)` and use a try-finally block where the finally calls `executor.shutdown(wait=False)`; inside the try block, initialise `results` as an empty dict; run a retry loop with `for attempt in range(int(max_retries) + 1):`; inside the loop, collect `unresolved` as the subset of agent_dispatch keys not yet in results; if unresolved is empty, break; submit one future per unresolved agent: `pending = {name: executor.submit(fn, *args) for name, (fn, args) in unresolved items}`; for each name and future in pending, call `future.result(timeout=float(timeout_seconds))` inside a try block, store the result under the name on success, and on TimeoutError or Exception call `future.cancel()` and continue; after the retry loop, for any agent name still not in results, set `results[name] = _fallbacks[name].copy()` where copy is called only if the fallback is a dict; assemble `agent_outputs` as a dict with keys technical, fundamentals, sentiment, macro, and risk, each mapped to the corresponding entry in results; return `aggregate_signals(agent_outputs)`

9. Create `tests/test_parallel_runner.py` — no real threads or HTTP calls; mock all five downstream module functions and `aggregate_signals`; use `@patch("data.parallel_runner.get_stock_history")`, `@patch("data.parallel_runner.get_fundamentals")`, `@patch("data.parallel_runner.generate_recommendation")`, `@patch("data.parallel_runner.analyze_sentiment")`, `@patch("data.parallel_runner.calculate_risk_metrics")`, and `@patch("data.parallel_runner.aggregate_signals")`; the `ThreadPoolExecutor` does not need mocking because mock functions return immediately — no real timeout occurs; cover the following test classes: TestOutputSchema (return dict has exactly the four keys; final_action is a string and one of BUY/SELL/HOLD; confidence is a float in zero to one; conflicts is a list); TestAllAgentsSucceed (when all mocks return valid results, aggregate_signals is called exactly once with an agent_outputs dict that has keys technical, fundamentals, sentiment, macro, and risk; result flows through); TestAgentFailureIsolation (when the technical agent raises an exception, result still has all four keys; when the sentiment agent raises an exception, result still valid; when all four voting agents raise, result is still valid and aggregate_signals is called); TestTimeoutGuard (when timeout_seconds is zero, returns the empty result dict immediately without calling any agent mock; when timeout_seconds is negative, same); TestNewsShortCircuit (when news_texts is provided as a non-empty string, the news agent function is never called; when news_texts is None, the news agent function is called and its return value is passed to analyze_sentiment); TestRetryBehaviour (when max_retries is zero, aggregate_signals is still called; when max_retries is two and an agent succeeds on the second attempt, its result is used not the fallback — use a side_effect list on the mock to raise once then succeed); TestFallbackConstants (when all five main agents raise, all agent_outputs values match the expected fallbacks; risk fallback has level "LOW"; voting agent fallbacks have action "HOLD" and confidence 0.0); TestComputeRsi (import `_compute_rsi` directly; fewer than 15 prices returns None; exactly 15 prices returns a float in zero to 100; all-same prices return a float or None without raising; RSI for a sequence of all-increasing prices is above 50; RSI for all-decreasing is below 50); TestWrapperTranslations (import `_run_technical_agent` directly and mock its dependencies: generate_recommendation returning title-case "Buy" must produce uppercase "BUY" in the wrapper output; import `_run_sentiment_agent` directly and mock analyze_sentiment: score 1 must produce action "BUY", score negative-one must produce "SELL", score 0 must produce "HOLD"; import `_run_risk_agent` directly and mock both get_stock_history and calculate_risk_metrics: when calculate_risk_metrics returns risk_level "HIGH", output must have level "HIGH"; when risk_level is None, output must have level "LOW")

---

## N — Norms

### Python Pipeline Norms

- Every public function has a single outer `try/except Exception` boundary — it never raises to the caller
- Return dicts use Python-native types only — wrap all computed floats with `float()`
- Module-level constants for all decision parameters and fallback values — no magic literals inside function bodies
- `_EMPTY_RESULT` is always returned via `.copy()` — never return the constant itself
- Private helpers and wrappers are prefixed with underscore; the public function is the thin orchestrator
- No new packages beyond what is already in `requirements.txt` — `concurrent.futures` is Python stdlib
- Python 3.9 compatibility — no bare `X | Y` union type hints; no walrus operator in complex positions
- Never modify existing `data/` modules — this story adds a coordinator, not a refactor

---

## S — Safeguards

### General Pipeline Safeguards

- Never raise an exception to the caller — all error paths return `_EMPTY_RESULT.copy()`
- Never mutate any `_*_FALLBACK` constant or `_EMPTY_RESULT` at runtime — always `.copy()` before returning
- Never return a non-float confidence value from any wrapper — always wrap with `float()`
- Do not import private helpers or constants from other `data/` modules

### Feature-Specific Safeguards

- RSI computation requires more than `period` price rows — guard `len(close_prices) <= period` and return `None`; `generate_recommendation` handles `rsi=None` safely via `_INVALID_RSI_FALLBACK`
- Shape-mismatch check before returning from each wrapper: every voting agent wrapper must return a dict with exactly two keys, action as an uppercase string and confidence as a float; the risk wrapper must return a dict with exactly one key, level, as a string; returning the wrong shape causes `_parse_agent_entry` to return None and silently drops the agent from the vote
- `generate_recommendation` returns title-case action — the technical wrapper MUST call `.upper()` before building its return dict; forgetting this silently disqualifies the technical agent
- `future.cancel()` on a running thread is advisory and does not stop the thread — do not assume the thread has stopped after calling cancel; retry submissions may run concurrently with prior timed-out attempts; keep `timeout_seconds` well above expected agent latency
- `executor.shutdown(wait=False)` must always run — place it in a `finally` block so it executes even if the retry loop raises
- `range(max_retries + 1)` not `range(max_retries)` — `max_retries=0` must mean exactly one attempt; using `range(max_retries)` with value 0 produces an empty range and zero attempts, always returning the fallback
- `calculate_risk_metrics` returns key `risk_level`; `aggregate_signals` reads key `level` — the risk wrapper must remap; using the wrong key causes the risk penalty to silently default to 1.0
- `news_texts=""` (empty string, not None) passes the `is not None` check and skips the news agent — this is intentional; `analyze_sentiment("")` handles it safely via `_EMPTY_INPUT_FALLBACK`
- Do not pass `timeout_seconds` as an integer directly to `future.result(timeout=...)` — wrap with `float()` to avoid type-related edge cases

---

## Change Log

- 2026-07-03: Initial canvas generated from analysis `2026-07-03-parallel-execution-runner-analysis.md`
