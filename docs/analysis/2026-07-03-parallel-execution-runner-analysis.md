# Analysis: Parallel Execution Runner
Date: 2026-07-03
Story: 2026-07-03-parallel-execution-runner-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline with 18 existing modules in `data/`. No web framework, ORM, or persistence layer. `concurrent.futures`, `asyncio`, and `ThreadPoolExecutor` have zero current usages in the codebase — this story introduces the first concurrent execution primitive. All 6 target agents are already present as synchronous functions in separate modules. The critical new insight is that three of the six agent functions produce output shapes that do not match the shape `aggregate_signals` expects — each wrapper must perform a translation step before handing off.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `get_stock_history(symbol, start, end)` | `data/stock.py:7` | Returns `list[dict]` with keys `date, open, high, low, close, volume`; no RSI field — RSI must be computed by the wrapper |
| `get_fundamentals(symbol)` | `data/stock.py:75` | Returns 5-key dict: `pe_ratio, pb_ratio, debt_to_equity, eps_last, eps_surprise`; does NOT produce an action or confidence — wrapper must derive both |
| `generate_recommendation(rsi, eps_surprise, pe_ratio)` | `data/screener.py:24` | Returns `{action, confidence, reason}` with title-case action ("Buy"/"Sell"/"Hold"); wrapper must normalise to uppercase for `aggregate_signals` |
| `analyze_sentiment(news_text)` | `data/sentiment.py:37` | Returns `{sentiment, score, reason}` — shape does NOT match `{action, confidence}`; returns `_EMPTY_INPUT_FALLBACK` (Neutral/score=0) when `news_text.strip()` is empty — stub news agent is already safe |
| `calculate_risk_metrics(weights, returns_data, ...)` | `data/risk.py` | Expects `weights: dict[str, float]` and `returns_data: dict[str, list[dict]]`; for single-ticker run, wrapper supplies `{ticker: 1.0}` and `{ticker: history}`; returns 6-key dict including `risk_level` |
| `aggregate_signals(agent_outputs)` | `data/meta_agent.py:77` | Expects `agent_outputs["technical"|"fundamentals"|"sentiment"|"macro"]` each as `{action (uppercase), confidence (float)}`; `agent_outputs["risk"]` as `{"level": str}` — note key is `"level"`, not `"risk_level"` |
| `_SIGNAL_AGENT_KEYS` | `data/meta_agent.py:8` | `("technical", "fundamentals", "sentiment", "macro")` — the 4 voting agents; `"risk"` and `"news"` are outside this tuple |
| `_RISK_PENALTIES` | `data/meta_agent.py:12` | `{"LOW": 1.0, "MEDIUM": 1.0, "HIGH": 0.80, "CRITICAL": 0.60}` — risk agent output must map `risk_level` to one of these exact strings |
| `_SENTIMENT_SCORE_MAP` | `data/sentiment.py:12` | `{"Positive": 1, "Neutral": 0, "Negative": -1}` — use to derive action from `analyze_sentiment` output: `+1 → "BUY"`, `0 → "HOLD"`, `-1 → "SELL"` |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/parallel_runner.py` | New module | Entire module is new |
| `run_agents_parallel(ticker, start, end, news_texts, timeout_seconds, max_retries)` | Public function | Main entry point; thin orchestrator |
| `_EMPTY_RESULT` | Module-level constant | `{final_action: "HOLD", confidence: 0.0, reasoning: "", conflicts: []}` — same shape as `aggregate_signals` fallback |
| `_run_technical_agent(ticker, start, end)` | Private wrapper | Calls `get_stock_history` → computes RSI from close prices via `_compute_rsi` → calls `get_fundamentals` → calls `generate_recommendation` → normalises title-case action to uppercase |
| `_compute_rsi(close_prices, period=14)` | Private helper | Computes standard Wilder RSI from a list of close floats; numpy available; returns `float | None`; needed because no existing module exposes RSI |
| `_run_fundamentals_agent(ticker)` | Private wrapper | Calls `get_fundamentals`; derives action from `eps_surprise` (positive→BUY, negative→SELL, None/zero→HOLD); derives confidence from data availability |
| `_run_sentiment_agent(news_texts)` | Private wrapper | Calls `analyze_sentiment`; maps `score` to action (+1→"BUY", 0→"HOLD", -1→"SELL"); maps sentiment string to confidence ("Positive"→0.75, "Neutral"→0.50, "Negative"→0.75) |
| `_run_macro_agent(ticker)` | Stub wrapper | Returns `_MACRO_FALLBACK = {"action": "HOLD", "confidence": 0.0}` — placeholder for future macro data source |
| `_run_news_agent(ticker)` | Stub wrapper | Returns `_NEWS_FALLBACK = ""` — placeholder for future news API; empty string is safe input for `analyze_sentiment` |
| `_run_risk_agent(ticker, start, end)` | Private wrapper | Calls `get_stock_history` then `calculate_risk_metrics(weights={ticker: 1.0}, returns_data={ticker: history})`; remaps `risk_level` to `{"level": risk_level or "LOW"}` |
| `_run_with_retry(fn, args, executor, timeout_seconds, max_retries, fallback)` | Private helper | Shared retry+timeout loop; submits `fn(*args)` to the provided executor, calls `future.result(timeout)`, catches `TimeoutError` and `Exception`; returns `fallback` after all retries exhausted; `range(max_retries + 1)` ensures `max_retries=0` means exactly one attempt |
| `_TECHNICAL_FALLBACK` | Module-level constant | `{"action": "HOLD", "confidence": 0.0}` — returned when technical agent fails all retries |
| `_FUNDAMENTALS_FALLBACK` | Module-level constant | `{"action": "HOLD", "confidence": 0.0}` |
| `_SENTIMENT_FALLBACK` | Module-level constant | `{"action": "HOLD", "confidence": 0.0}` |
| `_MACRO_FALLBACK` | Module-level constant | `{"action": "HOLD", "confidence": 0.0}` |
| `_RISK_FALLBACK` | Module-level constant | `{"level": "LOW"}` — LOW applies no penalty in `aggregate_signals` |
| `_NEWS_FALLBACK` | Module-level constant | `""` — empty string; `analyze_sentiment` returns Neutral/0 for empty input |
| `tests/test_parallel_runner.py` | Test file | Must mock all 5 imported downstream functions and `aggregate_signals`; `ThreadPoolExecutor` is real (no mock needed — it executes synchronously in tests because mock functions return immediately) |

---

## Strategic Approach

Build `data/parallel_runner.py` as a thin concurrency coordinator: six private agent wrappers run in parallel via a single `ThreadPoolExecutor`, a shared `_run_with_retry` helper enforces timeout and retry semantics per-agent, and the orchestrator assembles results into the `aggregate_signals` contract. All translation between existing function output shapes and the meta_agent input shape happens inside the individual wrappers — the orchestrator itself only collects results and calls `aggregate_signals`. This keeps each wrapper independently testable and makes the three shape-mismatch problems (RSI computation, action normalisation, score-to-action mapping) visible and isolated within a single file.

---

## Key Design Decisions

- **`ThreadPoolExecutor` not asyncio:** All 6 downstream functions make blocking I/O calls (yfinance HTTP, Anthropic HTTP, numpy). Wrapping them in `async def` would still block the event loop unless each was moved to `loop.run_in_executor`. `ThreadPoolExecutor` with `max_workers=6` achieves true I/O parallelism with zero changes to existing modules.
- **`_compute_rsi` inline in `parallel_runner.py`:** `get_stock_history` returns OHLCV with no RSI; `get_fundamentals` also has no RSI. Wilder RSI (14-period) requires only `numpy` (already in `requirements.txt`). Passing `rsi=None` to `generate_recommendation` produces `_INVALID_RSI_FALLBACK` with `confidence=0.0` — making the technical agent a guaranteed non-voter. Adding `_compute_rsi` is the only way to make the technical agent meaningful.
- **`_run_with_retry` shared helper:** Five of six agents share identical retry semantics; one helper eliminates five identical retry loops and makes timeout/retry behaviour testable in isolation without spawning real threads.
- **`risk_level` → `level` remapping:** `calculate_risk_metrics` returns key `"risk_level"`; `aggregate_signals` reads `agent_outputs["risk"].get("level")`. The wrapper must remap: `{"level": metrics.get("risk_level") or "LOW"}`.
- **`news_texts` short-circuit:** When the caller provides a non-None `news_texts`, `_run_news_agent` is not submitted to the executor — it would be a wasted worker slot on a stub. When `news_texts` is None, the news agent runs in the main parallel batch before sentiment is assembled.
- **`range(max_retries + 1)` in retry loop:** `max_retries=0` must mean exactly one attempt. `range(0)` is empty; `range(max_retries + 1)` with `max_retries=0` gives `range(1)` — one iteration, no retry.
- **`future.cancel()` after `TimeoutError` is advisory:** On a running `ThreadPoolExecutor` thread, `cancel()` is a no-op. The thread continues to completion in the background. This is acceptable for I/O-bound agents but means retry submissions may overlap with still-running previous attempts.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| RSI not available from existing functions | High | `generate_recommendation` requires RSI; neither `get_stock_history` nor `get_fundamentals` provides it. `_compute_rsi` must be added. Insufficient history (< 15 rows) → return `None` → `generate_recommendation` uses `_INVALID_RSI_FALLBACK` (confidence=0.0) |
| Output shape mismatches in 3 of 6 agents | High | `analyze_sentiment` returns `{sentiment, score, reason}` not `{action, confidence}`; `generate_recommendation` returns title-case action; `calculate_risk_metrics` uses `risk_level` not `level`. Missing any normalisation → `_parse_agent_entry` returns None → agent silently skipped in vote with no error |
| `future.cancel()` non-preemptive | Medium | Timed-out threads continue running; on retry, up to 2× `max_workers` threads may be live simultaneously. Mitigate by keeping `timeout_seconds` longer than expected agent latency |
| Single-ticker `calculate_risk_metrics` with short history | Medium | Requires at least 3 price rows. Short date range → risk agent returns `_EMPTY_RESULT` with `risk_level=None` → wrapper remaps to `"LOW"` → no penalty applied (intentionally safe default) |
| All 4 voting agents fall back to HOLD/confidence=0.0 | Medium | `_weighted_vote` returns HOLD; `_compute_confidence` returns 0.0. Result is valid dict with `confidence=0.0` — caller must interpret low confidence as "no signal" |
| `max_retries=0` off-by-one | Low | `range(max_retries)` with `max_retries=0` gives empty range → zero attempts → always returns fallback. Must use `range(max_retries + 1)` |
| `executor.shutdown(wait=False)` leaves background threads | Low | Threads mid-execution when orchestrator returns continue to completion. Acceptable for a pipeline tool; documents as known behaviour |
| `news_texts=""` (empty string, not None) | Low | Empty string passes `is not None` check; `_run_news_agent` skipped; `analyze_sentiment("")` → `_EMPTY_INPUT_FALLBACK` (Neutral/0/HOLD). Safe but caller should know empty string != no news |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns 4-key dict with valid final_action/confidence/reasoning/conflicts | Needs work | Satisfied by passing assembled `agent_outputs` through `aggregate_signals` |
| All 6 agents complete within timeout → all used in aggregation | Needs work | `_run_with_retry` resolves all 6 futures within timeout |
| One agent raises exception on all retries → fallback, others unaffected | Needs work | `_run_with_retry` catches `Exception`, returns per-agent fallback |
| One agent times out on all retries → fallback, others unaffected | Needs work | `_run_with_retry` catches `TimeoutError` from `future.result(timeout)` |
| All 6 agents fail → valid fallback dict still reaches `aggregate_signals` | Needs work | All 6 fallbacks are valid `{action, confidence}` or `{level}` shapes |
| `news_texts=None` → news agent invoked → output to sentiment | Needs work | Conditional branch in orchestrator; stub returns `""` which is safe |
| `news_texts` provided → news agent NOT called | Needs work | Short-circuit branch; test verifies news agent mock is NOT called |
| `timeout_seconds <= 0` → `_EMPTY_RESULT.copy()` immediately | Needs work | Pre-flight guard before executor creation |
| `max_retries=0` → each agent attempted exactly once | Needs work | `range(max_retries + 1)` with value 0 → single iteration |
| Orchestrator-level exception → `_EMPTY_RESULT.copy()`, never raises | Needs work | Outer `try/except Exception` wraps entire function body |

---

## Dependencies

| Module | Role | Change Required |
|--------|------|----------------|
| `data/stock.py` | Provides `get_stock_history` (technical + risk agents) and `get_fundamentals` (technical + fundamentals agents) | None — read-only consumer |
| `data/screener.py` | Provides `generate_recommendation` for technical agent | None — wrapper normalises title-case output to uppercase |
| `data/sentiment.py` | Provides `analyze_sentiment` for sentiment agent | None — wrapper maps `score` to action |
| `data/risk.py` | Provides `calculate_risk_metrics` for risk agent | None — wrapper remaps `risk_level` to `level` |
| `data/meta_agent.py` | Provides `aggregate_signals` as final aggregation step | None — read-only consumer |
| `concurrent.futures` | Provides `ThreadPoolExecutor` and `Future` | Python stdlib — first use in this codebase |
| `numpy` | Required by `_compute_rsi` | Already in `requirements.txt` — no new dependency |
