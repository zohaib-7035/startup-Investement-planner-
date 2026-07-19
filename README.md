# VC Brain — Agentic Founder Intelligence

**An offline-safe, multi-agent pipeline that sources, screens, and generates evidence-backed investment memos for startup founders — with full agentic traceability showing exactly which data point drove each conclusion.**

---

## What VC Brain Does (and Does NOT Do)

**Does:**
- Source founders via inbound applications or outbound GitHub scans, unified in one UI
- Score founders on three independent axes (Founder / Market / Idea-vs-Market) — axes are **never combined into a single score**
- Generate investment memos where every claim is tagged as `verified`, `unverifiable`, or `contradicted` against real signals
- Flag "not disclosed" sections explicitly rather than fabricating content
- Produce a chain-of-thought reasoning log: each conclusion cites the exact data point that drove it
- Run fully offline against synthetic demo profiles; Ollama only needed for claim extraction

**Does NOT:**
- Make final investment decisions — the human investor is always in the loop
- Replace legal, financial, or technical due diligence
- Guarantee accuracy of third-party data sources (GitHub signals are heuristic proxies)
- Store or transmit any founder data externally

---

## Architecture

VC Brain evolved from an AI Stock Intelligence Platform (multi-agent pipeline using Ollama + FRED + Yahoo Finance). The agents were repurposed for founder discovery — the same parallel runner, evidence-chain pattern, and trust-score mechanism that tracked macro signals now tracks founder signals from GitHub.

```
┌─────────────────────────────────────────────────────────┐
│                   Flask Dashboard (app.py)               │
│  /api/founders  /api/screen/<idx>  /api/thesis           │
└──────────┬───────────────────┬───────────────────────────┘
           │                   │
    ┌──────▼──────┐    ┌───────▼──────────────────┐
    │  sourcing.py │    │    scoring_engine.py      │
    │  inbound +   │    │  3-axis screening:        │
    │  outbound    │    │  founder / market /       │
    │  profiles    │    │  idea-vs-market           │
    └─────────────┘    └───────────────────────────┘
                               │
               ┌───────────────┼──────────────────┐
               │               │                  │
    ┌──────────▼──┐  ┌─────────▼─────┐  ┌────────▼──────┐
    │ trust_score │  │ memo_generator│  │ reasoning_log │
    │ extract +   │  │ evidence-backed│  │ chain-of-thought│
    │ verify claims│  │ memos with gap │  │ per conclusion │
    │             │  │ flagging       │  │ data citation  │
    └─────────────┘  └───────────────┘  └───────────────┘
```

**Key modules:**

| Module | Responsibility |
|--------|---------------|
| `data/sourcing.py` | Load/scan inbound + outbound founder profiles |
| `data/founder_signals.py` | 5 GitHub signals: commit frequency, star growth, contributor count, recency, tech stack depth |
| `data/scoring_engine.py` | Three-axis screening; thesis matching; risk flags |
| `data/thesis_engine.py` | Configurable ThesisConfig (sectors, stages, check size, risk appetite) |
| `data/trust_score.py` | Claim extraction (LLM, offline fallback) + rule-based signal verification |
| `data/memo_generator.py` | Investment memo generation; "not disclosed" gap flagging |
| `data/reasoning_log.py` | Agentic traceability: chain-of-thought reasoning log with data citations |
| `data/risk_flags.py` | Four risk categories: solo founder, stale repo, missing data, claim contradiction |

---

## How to Run

### Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai) (only needed for claim extraction; all other features are offline-safe)

### Setup

```bash
git clone <repo>
cd vc-brain
pip install -r requirements.txt

# Optional — for LLM-powered claim extraction
ollama pull llama3.2:3b
ollama serve
```

### Run the dashboard

```bash
python app.py
```

Open `http://localhost:5000` — navigate to **Sourcing** in the sidebar to load demo founders.

### Environment variables (all optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model for claim extraction |
| `FLASK_PORT` | `5000` | Dashboard port |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |

---

## Demo Flow

1. **Sourcing** — Load the 19 synthetic demo profiles (mix of inbound + outbound); note the `outbound` chip on GitHub-scanned founders
2. **Screen a founder** — Click Screen on any row to run the full pipeline
3. **Screening view** — See the three axes displayed separately with scores, trend arrows, and evidence bullets; check the thesis match result and risk flags
4. **Memo view** — Every claim carries a `verified` / `unverifiable` / `contradicted` badge; "not disclosed" sections are flagged explicitly
5. **Reasoning panel** — Expand "Show reasoning" on the Screening view to see the full chain-of-thought log

**Demo highlights:**
- **Priya Venkatesan / FinAI Labs** — inbound; `total_stars=92` vs. `claimed_users=48000` triggers a `contradicted` badge
- **Devon Marsh / TractionMax** — `total_stars=3`, `recency=210 days`, claimed 200k users — high-severity contradiction
- **Sofia Andersson / DeployKit** — outbound-sourced; strong commit signals

---

## Tests

```bash
pytest tests/ -v
```

Key test suites:

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_reasoning_log.py` | 11 | ReasoningLog: axis steps, claim steps, gap filtering, placeholder sanitisation, ISO timestamps |
| `test_scoring_engine.py` | 20+ | Three-axis scoring, FounderMemory persistence, thesis matching |
| `test_trust_score.py` | 15+ | Claim extraction (mocked LLM), verify_claim signal matching, contradictions |
| `test_memo_generator.py` | 10+ | Memo sections, gap flagging, "not disclosed" behaviour |
| `test_thesis_engine.py` | 8+ | ThesisConfig rules, PASS/FAIL/WATCHLIST verdicts |
| `test_risk_flags.py` | 8+ | All four risk categories and severity levels |
| `test_sourcing.py` | 6+ | Inbound/outbound loading, source filtering |

All tests run offline — no Ollama or GitHub API calls required.
