# VC Brain — Startup Investment Intelligence

A multi-agent AI pipeline that sources, scores, and generates investment memos for startup founders.
Repurposed from AI-Stock-Intelligence-Platform for the VC Brain hackathon.
No paid APIs — runs locally using GitHub REST API (free/unauthenticated) and Ollama (local LLM).

---

## What's Working vs. Stubbed

| Module | Status | Notes |
|--------|--------|-------|
| `data/founder_data.py` | **Working** | GitHub profile fetch (top-10 repos); pitch deck text/PDF ingestion with regex heuristics |
| `data/founder_signals.py` | **Working** | 5 signals: commit_frequency, star_growth, contributor_count, recency, tech_stack_depth |
| `data/thesis_engine.py` | **Working** | Configurable ThesisConfig; named-rule verdicts (PASS/FAIL/WATCHLIST) |
| `data/risk_flags.py` | **Working** | 4 categories: solo_founder, stale_repo, missing_data, claim_contradiction |
| `data/decision_engine.py` | **Stub axes** | AxisScore + DecisionResult implemented; founder/market/idea axis computations return 0.5 stub values |
| `data/memo_generator.py` | **Working** | Required sections always present; optional sections default to "[Not Disclosed]" |
| `data/parallel_runner.py` | **Working** | Generic dispatch dict interface; per-agent timeout + retry; no stock-specific code |
| `data/market_context.py` | **Stub** | Public surface of macro_data.py preserved; returns empty dict |
| `data/knowledge_graph.py` | **Retained** | Ollama triple extraction; system prompt is finance-flavoured (swap in Story 4) |
| `data/graph_reasoning.py` | **Retained** | BFS impact analysis; domain-agnostic; ready for reuse |
| `data/vector_store.py` | **Retained** | ChromaDB RAG; out of scope v1 |
| `data/edgar_client.py` | **Retained** | SEC EDGAR filings; out of scope v1 |
| `POST /source` | **Working** | Accepts `{"github": "username"}` or `{"pitch_deck": "text"}` |
| `POST /score` | **Working** | Returns signals, thesis_result, risk_flags, decision |
| `POST /memo` | **Working** | Returns InvestmentMemo JSON with [Not Disclosed] for absent optional sections |

**Deleted (out of scope):** backtester, notifier, portfolio, scenario, market_data, openbb_client, meta_agent, report, stock, signals, screener, risk

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Ollama for the `/api/knowledge-graph` route:
```bash
ollama serve
ollama pull llama3.2:3b
```

## Running

```bash
python app.py
# → http://localhost:5000

 #* Running on all addresses (0.0.0.0)
 #* Running on http://127.0.0.1:5000
 #* Running on http://192.168.18.116:5000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/source` | Fetch founder profile from GitHub or pitch deck |
| `POST` | `/score` | Run 3-axis scoring pipeline |
| `POST` | `/memo` | Generate investment memo |
| `GET` | `/api/status` | Health check (Ollama, VADER) |
| `POST` | `/api/knowledge-graph` | Extract entity triples from text |

### /source example
```json
{"github": "torvalds"}
{"pitch_deck": "We are raising Series A for our FinTech startup with 50,000 users."}
```

### /score example
```json
{
  "profile": {"name": "Ada", "sector": "FinTech", "stage": "Series A", ...},
  "thesis_config": {"sectors": ["FinTech"], "stages": ["Series A"], "risk_appetite": "medium"}
}
```

## Running Tests

```bash
python -m pytest tests/ -v
```

180 tests collected. 170 pass. 10 pre-existing failures in retained RAG/graph modules (identical to source repo).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.9 + Flask |
| LLM | Ollama (`llama3.2:3b`) — local, free |
| Founder data | GitHub REST API v3 — unauthenticated, free |
| PDF parsing | PyPDF2 |
| Vector store | ChromaDB + sentence-transformers (retained, unused v1) |

---

## Real API Calls vs. Stubbed/Synthetic

| Component | Status | Notes |
|-----------|--------|-------|
| GitHub repository search (`outbound_scan(source="github")`) | **Real API** | Unauthenticated GitHub `/search/repositories`; 60 req/hr limit; capped at 10 results per call |
| Hacker News connector (`outbound_scan(source="hacker_news")`) | **Stub** | Returns empty list; real implementation would use Algolia HN Search API (no key required) at `https://hn.algolia.com/api/v1/search?tags=show_hn` |
| ProductHunt connector (`outbound_scan(source="product_hunt")`) | **Stub** | Returns empty list; real implementation requires OAuth client token from ProductHunt developer portal |
| Synthetic demo dataset (`load_sample_founders()`) | **Synthetic** | 18 pre-seeded fictional profiles in `data/sample_founders.json`; 3 sectors, 3 seeded contradictions; loaded as demo fallback when live scanning is slow or rate-limited |
