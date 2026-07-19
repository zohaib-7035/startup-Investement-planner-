# VC Brain — Agentic Founder Intelligence

> An offline-safe, multi-agent AI system that sources, screens, and generates evidence-backed investment memos for startup founders — with full agentic traceability.

---

## Overview

VC Brain transforms the relationship-gated venture capital process into a transparent, data-driven screening engine. It discovers founders via GitHub and inbound pitch decks, evaluates them across three independent scoring axes, verifies their claims against real signals, and produces structured investment memos — all without requiring any paid API keys.

---

## Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Web Framework** | Python 3.9+ / Flask | Stateless REST API endpoints; lightweight WSGI app |
| **Production Server** | Gunicorn | Multi-worker WSGI serving on Render (configured via `render.yaml`) |
| **Local LLM** | Ollama (`llama3.2:3b`) | Claim extraction, NL multi-attribute queries, knowledge graph extraction |
| **Sentiment Analysis** | VADER (`vaderSentiment`) | Offline financial news sentiment — no API key, no cost |
| **Vector Store** | ChromaDB (persistent) | Stores and retrieves SEC filing chunks for RAG |
| **Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`) | Encodes text chunks and questions for semantic similarity search |
| **PDF Ingestion** | PyPDF2 | Reads pitch deck PDFs into raw text |
| **HTML Scraping** | BeautifulSoup4 + lxml | Parses SEC EDGAR HTML filing pages |
| **GitHub Data** | GitHub REST API v3 (unauthenticated) | Fetches public repo metrics — respects 60 req/hr free tier |
| **SEC Filings** | SEC EDGAR public API | Downloads 10-K filings by ticker → CIK resolution |
| **Concurrency** | `concurrent.futures.ThreadPoolExecutor` | Runs scoring agents in parallel with per-agent timeout and retry |
| **Frontend** | HTML5 / Vanilla JavaScript / Custom CSS | Single-page dashboard; no framework dependency |
| **Dependency Isolation** | `python-dotenv` | Loads environment variables from `.env` for local development |

---

## Architecture

VC Brain is organized into three horizontal layers executing a four-stage pipeline.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EXPERIENCE LAYER  (Frontend)                      │
│              templates/index.html — Notion-style SPA                 │
│         Vanilla JS + Custom CSS (HSL palette, glassmorphism)         │
└───────────────────────────┬──────────────────────┬───────────────────┘
                            │   REST / JSON         │
┌───────────────────────────▼──────────────────────▼───────────────────┐
│                  INTELLIGENCE LAYER  (app.py + data/)                │
│                                                                      │
│  [Sourcing]          [Signals]        [Scoring Engine]               │
│  sourcing.py  ──►  founder_signals.py ──► scoring_engine.py         │
│  founder_data.py                          thesis_engine.py           │
│                                           parallel_runner.py         │
│                                                                      │
│  [Diligence]         [Knowledge Graph]    [RAG / EDGAR]             │
│  trust_score.py ──► knowledge_graph.py   vector_store.py            │
│  risk_flags.py       graph_reasoning.py  rag_query.py / rag_answer  │
│                                          edgar_client.py / chunker   │
│                                                                      │
│  [Decision]          [Sentiment]                                     │
│  memo_generator.py   sentiment.py                                    │
│  reasoning_log.py                                                    │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                    MEMORY LAYER  (Persistence)                       │
│   data/founder_memory.json  ──  JSON score history per founder       │
│   data/thesis_config.json   ──  Saved investor mandate settings      │
│   .chroma/                  ──  ChromaDB vector store (SEC filings)  │
└──────────────────────────────────────────────────────────────────────┘
```

### Four-Stage Pipeline

```
Inbound Pitch Deck ──┐
                     ├──► [1. SOURCING] ──► [2. SCREENING] ──► [3. DILIGENCE] ──► [4. DECISION]
GitHub Outbound Scan ┘         │                  │                  │                  │
                          Junk filter        3-axis score      Claim extract       Memo + log
                          Profile parse      Thesis check      Claim verify        Risk flags
                          Signal extract     NL query          Trust score         Chain-of-thought
```

---

## Implementation

### 1. Sourcing (`data/sourcing.py`, `data/founder_data.py`)

Two entry points feed the same funnel:

- **Inbound**: `ingest_pitch_deck()` reads PDF or plain text and runs a fast junk filter (`FilterRejected` exception) that rejects submissions shorter than 50 characters or missing team and product signal keywords. Accepted decks map to `FounderProfile`.
- **Outbound**: `outbound_scan()` calls `GET /search/repositories` on the GitHub REST API (unauthenticated, 60 req/hr) using sector keywords. Matching repos are enriched and tagged as outbound. `activate()` generates a cold-outreach email template.
- **Demo mode**: `load_sample_founders()` reads `data/sample_founders.json` so the app works without any live API calls.

`FounderProfile` is a Python `dataclass` holding `name`, `company`, `sector`, `stage`, `github_url`, and a `key_signals` dict (star count, repo count, commit cadence, etc.).

`fetch_github_profile()` caps at 10 repos to stay within the free rate limit. Sector is inferred by keyword matching against `_SECTOR_KEYWORDS`; stage is extracted by regex from pitch text.

---

### 2. Signals (`data/founder_signals.py`)

`generate_founder_signals(profile)` computes developer-activity metrics from `key_signals`:

- **Commit frequency** — average commits per week over the last year
- **Star growth rate** — total stars / months since first push
- **Contributor count** — size of the external contributor base
- **Repo recency** — days since last push
- **Tech stack depth** — count of distinct programming languages used

Each metric returns a `{"score": 0-100, "direction": "up|down|neutral"}` dict so downstream axes can interpret signal direction, not just magnitude.

---

### 3. Scoring Engine (`data/scoring_engine.py`)

The engine runs **three fully independent axes** via `run_agents_parallel()` (backed by `concurrent.futures.ThreadPoolExecutor`). Axes are **never averaged or combined** — disagreement is preserved, not hidden.

| Axis | Driver | What it measures |
|:---|:---|:---|
| **Founder Axis** | Rule-based (offline-safe) | GitHub velocity, contributor growth, tech depth |
| **Market Axis** | Rule-based (offline-safe) | Sector trend signals, stage-market fit, market size indicators |
| **Idea-vs-Market Axis** | Ollama LLM + offline fallback | Semantic fit between the founder's product narrative and the target market |

`FounderMemory` is a JSON file store (`data/founder_memory.json`) keyed by `github_url` or `name::company`. Each screening appends the composite score to that founder's history list so trend analysis is possible across re-screens.

`query_founders()` accepts a natural-language string (e.g., `"technical founder, AI infra, enterprise traction"`) and uses Ollama to semantically filter pre-screened results — rule-based scoring runs first, then the LLM narrows the set.

---

### 4. Thesis Filter (`data/thesis_engine.py`)

`ThesisConfig` is a `dataclass` (persisted to `data/thesis_config.json`) that captures an investor's mandate:

- Allowed sectors and stages
- Check size range (`check_size_min` / `check_size_max`)
- Minimum ownership percentage
- Risk appetite flag

`evaluate_founder(profile, config)` returns a `ThesisResult` with `verdict` (`PASS` / `FAIL` / `WATCHLIST`) and lists of `matched_rules` and `failed_rules`. The API exposes `GET /api/thesis` and `POST /api/thesis` to read and update the config at runtime.

---

### 5. Trust Score & Claim Verification (`data/trust_score.py`)

**Claim extraction** (`extract_claims`): sends the founder's pitch text to Ollama with a structured system prompt instructing it to return a JSON array of `{claim_text, category, confidence_score, source_reference}`. Falls back to an empty list if Ollama is unavailable.

Claim categories: `traction`, `revenue`, `team`, `market_size`, `other`.

**Claim verification** (`verify_claim`): a pure rule-based function (always offline-safe). It cross-references each extracted claim against an `evidence` list built from `founder_signals` and `key_signals`. Returns `VerifiedClaim` with status:

| Status | Meaning |
|:---|:---|
| `verified` | Evidence corroborates the claim (e.g., high star count backs a "growing community" claim) |
| `unverifiable` | No relevant evidence signal exists to check against |
| `contradicted` | Evidence directly contradicts the claim (e.g., zero commits contradicts "actively shipping") |

---

### 6. Knowledge Graph (`data/knowledge_graph.py`, `data/graph_reasoning.py`)

`extract_relationships(text)` calls Ollama with a financial-relationship extraction prompt, returning a list of `{source, relation, target, confidence}` triples. Relations use uppercase canonical types (`SUPPLIER`, `COMPETITOR`, `INVESTOR`, `ACQUIRER`, etc.).

`analyze_impact(graph, disrupted_entity)` runs a **BFS traversal** over the adjacency list built from triples. Starting from the disrupted node, it walks outward, distinguishing directly affected nodes (depth 1) from indirectly affected nodes (depth 2+). Each step appends a reasoning chain entry so the propagation path is fully traceable.

---

### 7. RAG Pipeline (`data/vector_store.py`, `data/rag_query.py`, `data/chunker.py`, `data/edgar_client.py`)

The RAG subsystem supports question-answering over SEC 10-K filings:

- **`edgar_client.download_10k(ticker)`**: resolves a ticker to a CIK via the EDGAR company tickers endpoint, then fetches the filing index to download the raw HTML. BeautifulSoup + lxml strip HTML markup to plain text.
- **`chunker.py`**: splits the cleaned filing text into fixed-size overlapping chunks with metadata (`company`, `filing_type`, `filing_date`, `chunk_id`).
- **`vector_store.ingest_chunks()`**: encodes chunks with `sentence-transformers` (`all-MiniLM-L6-v2`) and inserts embeddings into a named ChromaDB collection (persistent on disk at `.chroma/`). Collection names are slugified as `{company}_{filing_type}`.
- **`rag_query.retrieve_chunks(question, collection_name)`**: encodes the question, queries ChromaDB for the top-N nearest chunks by cosine distance, and returns them with metadata and distance score.

---

### 8. Sentiment Analysis (`data/sentiment.py`)

`analyze_sentiment(news_text)` uses the VADER lexicon to classify financial news as `Positive`, `Neutral`, or `Negative`. VADER compound scores ≥ 0.05 → Positive; ≤ -0.05 → Negative; otherwise Neutral. Returns `{"sentiment", "score", "reason"}`. Fully offline — no model download, no API call.

---

### 9. Memo Generator (`data/memo_generator.py`)

`generate_memo(profile, screening, verified_claims)` assembles an `InvestmentMemo` dataclass with five `MemoSection` objects:

1. **Company Overview** — name, sector, stage, source
2. **Founder Assessment** — founder axis score, risk flags
3. **Market Opportunity** — market axis score, thesis alignment
4. **Traction & Evidence** — verified claims filtered to `traction` / `revenue` categories
5. **Risk & Gaps** — `RiskFlag` list + any sections with no disclosures

Sections without available data are explicitly marked `"[Not Disclosed]"` rather than omitted or fabricated — a deliberate design choice to prevent hallucination-driven investment decisions.

---

### 10. Risk Scanner (`data/risk_flags.py`)

`flag_risks(profile, signals)` produces a list of `RiskFlag` objects. Checks include:

- **Solo founder** — no co-founder signals in the pitch
- **Stale repository** — last push > 180 days ago
- **No traction evidence** — zero traction/revenue verified claims
- **Contradicted claims** — any `VerifiedClaim` with status `contradicted`
- **Missing key signals** — absent GitHub metrics (no repos, no stars)

---

### 11. Reasoning Log (`data/reasoning_log.py`)

`build_screening_log(profile, screening, verified_claims, idx)` constructs a `ScreeningLog` dataclass that records every inference step:

- Which axis scores were assigned and why
- Which claims were extracted and their verification status
- Which risk flags were raised
- Which thesis rules were matched or failed

This log is returned alongside the memo in the `/api/screen/<idx>` response so callers can audit every decision.

---

### 12. REST API (`app.py`)

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/` | Renders the SPA dashboard |
| `GET` | `/api/status` | Reports Ollama connectivity and VADER availability |
| `GET` | `/api/founders` | Lists all sample founders with index, sector, stage, source |
| `POST` | `/api/screen/<idx>` | Runs the full pipeline for founder at index `idx`; returns `screening`, `memo`, `reasoning_log`, `profile` |
| `GET` | `/api/thesis` | Returns the current `ThesisConfig` |
| `POST` | `/api/thesis` | Validates and persists a new `ThesisConfig` |
| `POST` | `/api/query` | Natural-language multi-attribute founder search |
| `POST` | `/api/knowledge-graph` | Extracts entity triples from text and optionally runs BFS impact analysis |
| `POST` | `/source` | (Legacy) Fetches a GitHub profile or ingests a pitch deck |

All endpoints return JSON. Error responses follow `{"error": "<message>"}` with standard HTTP status codes. The `/score` and `/memo` endpoints return `410 Gone` — callers should use `/api/screen/<idx>`.

---

### 13. Frontend (`templates/index.html`)

A single-page application served by Flask. No JavaScript framework — all interactivity is plain `fetch()` calls against the REST API. The UI uses:

- A custom HSL-based color token system with slate-dark background gradients
- Glassmorphism card components
- CSS transition animations for score badge reveals
- An interactive founder table with filter and sort controls
- A thesis configuration panel that `POST`s to `/api/thesis` on save

---

## Project Structure

```
startup-Investment-planner/
├── app.py                        # Flask app, routes, error handlers
├── requirements.txt              # Python dependencies
├── render.yaml                   # Render.com deployment config (Gunicorn)
├── run_server.bat                # Windows dev-server launcher
├── data/
│   ├── sample_founders.json      # Demo founder dataset
│   ├── thesis_config.json        # Persisted ThesisConfig (created at runtime)
│   ├── founder_memory.json       # Persisted score history (created at runtime)
│   ├── founder_data.py           # FounderProfile dataclass + GitHub/PDF ingestion
│   ├── sourcing.py               # Inbound/outbound sourcing funnel
│   ├── founder_signals.py        # GitHub developer-activity metrics
│   ├── scoring_engine.py         # 3-axis scoring + FounderMemory + NL query
│   ├── thesis_engine.py          # ThesisConfig evaluation
│   ├── trust_score.py            # LLM claim extraction + rule-based verification
│   ├── memo_generator.py         # Investment memo assembly
│   ├── risk_flags.py             # Risk flag scanner
│   ├── reasoning_log.py          # Chain-of-thought traceability log
│   ├── knowledge_graph.py        # Ollama entity-relationship extraction
│   ├── graph_reasoning.py        # BFS impact propagation analysis
│   ├── sentiment.py              # VADER financial news sentiment
│   ├── edgar_client.py           # SEC EDGAR 10-K downloader
│   ├── chunker.py                # Document chunker for RAG
│   ├── vector_store.py           # ChromaDB + sentence-transformers ingestion
│   ├── rag_query.py              # Semantic chunk retrieval
│   ├── rag_answer.py             # LLM answer generation over retrieved chunks
│   ├── decision_engine.py        # AxisScore dataclass
│   ├── market_context.py         # Market context helpers
│   ├── profile_advisor.py        # Advisor signal helpers
│   └── parallel_runner.py        # concurrent.futures agent dispatcher
├── templates/
│   └── index.html                # SPA dashboard (HTML5 / Vanilla JS / CSS)
└── tests/
    ├── test_scoring_engine.py
    ├── test_trust_score.py
    ├── test_memo_generator.py
    └── ...                       # One test file per data module
```

---

## Running Locally

### Prerequisites

- Python 3.9+
- Ollama (optional — the app runs fully offline without it via rule-based fallbacks)

```bash
# Install and start Ollama
ollama pull llama3.2:3b
ollama serve
```

### Install & Start

```bash
git clone https://github.com/zohaib-7035/startup-Investment-planner-.git
cd startup-Investment-planner-
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

### Environment Variables

| Variable | Default | Description |
|:---|:---|:---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | LLM model name |
| `FLASK_PORT` | `5000` | HTTP port |
| `FLASK_HOST` | `0.0.0.0` | Bind address |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `CHROMA_PERSIST_DIR` | `.chroma` | ChromaDB persistence directory |
| `SEC_USER_AGENT` | `stock-analyzer contact@example.com` | EDGAR required User-Agent header |

### Run Tests

```bash
pytest tests/ -v
```

---

## Deployment

The app ships with a `render.yaml` for zero-config deployment on [Render](https://render.com):

```yaml
services:
  - type: web
    name: vc-brain
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
```

Ollama is not available on Render's free tier — the app degrades gracefully to rule-based scoring for all LLM-dependent steps.
