# User Story: Parallel Execution Runner
Date: 2026-07-03
Source: Pasted text — Story 20: Parallel Execution

---

## Story 20: Execute All Pipeline Agents in Parallel and Aggregate into Meta Decision

**As a** quantitative analyst using the AI Stock Intelligence Platform,
**I want** all analysis agents to run concurrently for a given ticker with timeout and retry protection,
**So that** the full pipeline produces a final investment decision in the shortest possible wall-clock time, with individual agent failures isolated and never propagating to the final result.

### Scope In
- Single public function `run_agents_parallel(ticker, start, end, news_texts=None, timeout_seconds=30, max_retries=2)` in `data/parallel_runner.py`
- Six agent wrappers executed concurrently via `concurrent.futures.ThreadPoolExecutor` with `max_workers=6`:
  - `_run_technical_agent(ticker, start, end)` — calls `get_stock_history` then `generate_recommendation`
  - `_run_fundamentals_agent(ticker)` — calls `get_fundamentals`
  - `_run_sentiment_agent(news_texts)` — calls `analyze_sentiment` if `news_texts` is non-empty, otherwise returns fallback
  - `_run_macro_agent(ticker)` — stub returning HOLD/0.0 confidence (placeholder for future macro data source)
  - `_run_news_agent(ticker)` — stub returning empty news_texts string (placeholder for future news API)
  - `_run_risk_agent(ticker, start, end)` — calls `get_stock_history` then `calculate_risk_metrics`
- Per-agent retry loop: up to `max_retries` re-submissions on `TimeoutError` or any `Exception`
- Per-agent timeout enforced via `future.result(timeout=timeout_seconds)`
- Any agent that exhausts all retries returns its own `_FALLBACK` constant silently — never raises
- Assembly: collect the 6 results into the `agent_outputs` dict shape that `aggregate_signals` expects
  - `technical`, `fundamentals`, `sentiment`, `macro` → each `{"action": str, "confidence": float}`
  - `risk` → `{"level": str}` (modifier key, not a voting agent)
  - `news` agent output (news text string) is passed as input to `sentiment` agent, not included in `agent_outputs`
- Final step: call `aggregate_signals(agent_outputs)` from `data/meta_agent.py` and return its result
- Return type: same 4-key dict as `aggregate_signals` — `{final_action, confidence, reasoning, conflicts}`
- `_EMPTY_RESULT` fallback: `{"final_action": "HOLD", "confidence": 0.0, "reasoning": "", "conflicts": []}` — returned via `.copy()` on any unhandled exception in the orchestrator itself
- Executor cleanup: `ThreadPoolExecutor` always shut down via `executor.shutdown(wait=False)` after futures resolve

### Scope Out
- Fetching real news data from any external API (news_agent is a stub in this story)
- Real macro-economic data from any external API (macro_agent is a stub in this story)
- Streaming or progressive result updates — result is returned only when all futures resolve or time out
- Asyncio (`async/await`) — all existing agent functions are synchronous; `ThreadPoolExecutor` is the correct tool
- Modifying any existing agent module — this story adds a new coordinator only
- Portfolio-level or multi-ticker batch runs — one ticker per call
- Persisting or caching agent results between runs
- UI, REST API layer, or CLI entrypoint

### Acceptance Criteria

- **Given** a valid ticker, start date, and end date with all external data available,
  **when** `run_agents_parallel` is called,
  **then** it returns a dict with exactly the keys `final_action`, `confidence`, `reasoning`, and `conflicts`, where `final_action` is one of `"BUY"`, `"SELL"`, or `"HOLD"`, `confidence` is a float in `[0.0, 1.0]`, `reasoning` is a non-empty string, and `conflicts` is a list.

- **Given** all six agents complete within the timeout,
  **when** `run_agents_parallel` is called,
  **then** all six futures resolve and their results are used in the aggregation; no agent is skipped.

- **Given** one agent raises an exception on every attempt up to `max_retries`,
  **when** `run_agents_parallel` is called,
  **then** that agent's output is replaced with its fallback constant, the other five agents' results are used normally, and the function returns a valid aggregated result without raising.

- **Given** one agent times out (exceeds `timeout_seconds`) on every attempt up to `max_retries`,
  **when** `run_agents_parallel` is called,
  **then** that agent's future is cancelled, its output is replaced with its fallback constant, and the function returns a valid aggregated result without raising.

- **Given** all six agents fail (exception or timeout) on all retries,
  **when** `run_agents_parallel` is called,
  **then** all agent outputs are their respective fallbacks, and `aggregate_signals` still receives a valid `agent_outputs` dict; if `aggregate_signals` returns its own empty result, that is the return value.

- **Given** `news_texts` is `None`,
  **when** `run_agents_parallel` is called,
  **then** `_run_news_agent` is invoked to attempt news retrieval; its output (or fallback empty string) is passed to `_run_sentiment_agent` — no exception is raised regardless of news_agent outcome.

- **Given** `news_texts` is provided as a non-empty string,
  **when** `run_agents_parallel` is called,
  **then** `_run_news_agent` is NOT called and the provided `news_texts` value is passed directly to `_run_sentiment_agent`.

- **Given** `timeout_seconds` is 0 or negative,
  **when** `run_agents_parallel` is called,
  **then** it returns `_EMPTY_RESULT.copy()` immediately without spawning any futures.

- **Given** `max_retries` is 0,
  **when** `run_agents_parallel` is called,
  **then** each agent is attempted exactly once; failed agents use their fallback with no retry.

- **Given** any unhandled exception in the orchestrator itself (outside agent futures),
  **when** `run_agents_parallel` is called,
  **then** it returns `_EMPTY_RESULT.copy()` and never raises.

### Definition of Done
- [ ] `data/parallel_runner.py` implemented with `run_agents_parallel` matching the contract above
- [ ] `_EMPTY_RESULT` module-level constant; always `.copy()` on return
- [ ] Six `_run_*_agent` private wrappers — each has its own `_*_FALLBACK` constant and inner `try/except`
- [ ] `ThreadPoolExecutor` with `max_workers=6`; executor shutdown in `finally` block
- [ ] Per-agent retry loop with `TimeoutError` and general `Exception` catches
- [ ] `news_texts` short-circuit: skip `_run_news_agent` when provided; run it only when `None`
- [ ] `timeout_seconds <= 0` pre-flight guard returns `_EMPTY_RESULT.copy()`
- [ ] Output of `run_agents_parallel` passes through `aggregate_signals` — not a raw agent dict
- [ ] `tests/test_parallel_runner.py` written; all agent functions mocked via `@patch`
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_parallel_runner.py -v`
- [ ] Full suite still green: `& "Z:\python39\python.exe" -m pytest tests/ -v`
- [ ] `/test-review` run; Recommendation: Ready (no Meaningless, <25% Weak)

---
