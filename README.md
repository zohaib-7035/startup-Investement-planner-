# VC Brain — Agentic Founder Intelligence
> **An offline-safe, multi-agent AI operating system that sources, screens, and generates evidence-backed investment memos for startup founders — featuring full agentic traceability.**

---

## 🌟 Vision & Why It Matters
In traditional venture capital, **capital flows to who you know, not what you are building**. Founders stay invisible until they find the right warm intro. Diligence takes weeks, and promising builders are missed because their profiles are scattered across GitHub commits, pitch decks, and social footprints.

**VC Brain** transforms this relationship-gated system into an **equitable capital allocation engine**. It discovers exceptional founders early, scores them transparently on independent axes, and produces evidence-backed investment decisions in hours instead of weeks.

---

## 🧭 System Architecture & Flow

VC Brain is built on a structured, three-layered architecture (Memory, Intelligence, and Experience) executing a 4-stage pipeline: **Sourcing ➔ Screening ➔ Diligence ➔ Decision**.

```
                       ┌─────────────────────────────────────────────────────────┐
                       │                EXPERIENCE LAYER (HTML5/CSS)             │
                       │           Notion-Style UI Dashboard (index.html)        │
                       └────────────────────┬────────────────┬───────────────────┘
                                            │                │
                       ┌────────────────────▼────────────────▼───────────────────┐
                       │                   INTELLIGENCE LAYER (Python)           │
                       │   [Sourcing Filter]         ➔      [Scoring Engine]     │
                       │   data/sourcing.py                 data/scoring_engine.py
                       │   (Inbound/Outbound Funnel)        (3-Axis Screening)   │
                       └────────────┬────────────────────────────────┬───────────┘
                                    │                                │
                       ┌────────────▼────────────────────────────────▼───────────┐
                       │                     DILIGENCE & DECISION LAYER          │
                       │   [Trust Score Verification]➔      [Memo Generator]     │
                       │   data/trust_score.py              data/memo_generator.py
                       │   (Rule-based Claims Validation)   (Explicit Gap Flagging)
                       └────────────┬────────────────────────────────┬───────────┘
                                    │                                │
                       ┌────────────▼────────────────────────────────▼───────────┐
                       │                     MEMORY LAYER (Persistence)          │
                       │   [Founder Score History]   ➔      [Traceability Log]   │
                       │   data/founder_memory.json         data/reasoning_log.py
                       │   (JSON Persistent Database)       (Chain-of-Thought Logs)
                       └─────────────────────────────────────────────────────────┘
```

### 🔁 End-to-End Pipeline Execution Flow:
1. **Sourcing**: Founders enter via inbound pitch deck uploads (which go through a fast first-pass junk filter) or outbound automated GitHub scans.
2. **Screening**: The scoring engine runs parallel agents to evaluate the founder on three independent axes (Founder, Market, and Idea-vs-Market). Scores are *never* averaged or combined to hide disagreement.
3. **Diligence**: The LLM extracts specific founder assertions. A rule-based Validator cross-checks these claims against actual GitHub repository signals to determine trust status (`verified`, `unverifiable`, or `contradicted`).
4. **Decision**: The system compiles a structured investment memo, automatically marking missing variables as `[Not Disclosed]` rather than fabricating data. It appends an agentic chain-of-thought log showing exactly which data point drove each score.

---

## 🛠️ The Tech Stack

- **Backend Framework**: Python 3.9+ with Flask (lightweight, modular, and stateless API endpoints).
- **AI / LLM Engine**: Local [Ollama](https://ollama.ai) (running `llama3.2:3b`) for unstructured claim extraction and natural-language multi-attribute semantic queries.
- **Data Logic & Validation**: Pure Python mathematical and heuristic rule engines (ensures fast execution and robust offline fallback when LLM is unavailable).
- **Frontend Layer**: Single-Page Application (SPA) dashboard built with semantic HTML5, Vanilla JavaScript, and a customized premium CSS system (custom HSL color palette, slate-dark gradients, glassmorphism tokens, and responsive transitions).
- **Libraries**: `requests` (http calls), `PyPDF2` (pitch deck processing), `pytest` (comprehensive automated test suite).

---

## 📂 Codebase & Module Directory

| Module | Location | Responsibility |
| :--- | :--- | :--- |
| **Sourcing funnel** | [`data/sourcing.py`](file:///e:/startup-Investement-planner-/data/sourcing.py) | Ingests inbound decks & outbound GitHub scans. Implements the fast first-pass filter and activation email flow. |
| **Profile Parser** | [`data/founder_data.py`](file:///e:/startup-Investement-planner-/data/founder_data.py) | Ingests PDF/txt pitch decks and pulls public user metadata from the GitHub REST API. |
| **Signals Generator** | [`data/founder_signals.py`](file:///e:/startup-Investement-planner-/data/founder_signals.py) | Calculates developer metrics: commit frequency, star growth rate, contributor counts, repo recency, and tech stack depth. |
| **Scoring Engine** | [`data/scoring_engine.py`](file:///e:/startup-Investement-planner-/data/scoring_engine.py) | Executes multi-axis analysis. Implements persistent JSON `FounderMemory` and natural language queries. |
| **Thesis Filter** | [`data/thesis_engine.py`](file:///e:/startup-Investement-planner-/data/thesis_engine.py) | Evaluates candidates against custom investor mandates (sectors, stage, risk appetite). |
| **Trust Scorer** | [`data/trust_score.py`](file:///e:/startup-Investement-planner-/data/trust_score.py) | Extracts claims from text via local LLM and verifies them against repo data to calculate Trust Scores. |
| **Memo Builder** | [`data/memo_generator.py`](file:///e:/startup-Investement-planner-/data/memo_generator.py) | Assembles the final 5 required sections of the Investment Memo and handles gap-flagging. |
| **Risk Scanner** | [`data/risk_flags.py`](file:///e:/startup-Investement-planner-/data/risk_flags.py) | Scans for solo founders, stale repos, missing data, and high-severity claim contradictions. |
| **Traceability Log** | [`data/reasoning_log.py`](file:///e:/startup-Investement-planner-/data/reasoning_log.py) | Constructs step-by-step chain-of-thought logs detailing the logic behind each conclusion. |
| **UI Dashboard** | [`templates/index.html`](file:///e:/startup-Investement-planner-/templates/index.html) | Notion-style responsive investor interface with interactive charts, badges, and controls. |

---

## 📹 Tech Video Script & Presentation Guide (5 Minutes)

Use this structured outline to record a compelling hackathon submission video.

### **0:00 - 0:45 | The Pitch & Hook (Why VC Brain?)**
- **Action**: Share your screen showing the dashboard home screen or the "Sourcing" tab.
- **Talking Points**: 
  - *"Welcome to VC Brain. Traditional venture capital relies on who you know. We've built an AI-first operating system that changes this, scanning developer signals and pitch decks to back exceptional founders in 24 hours."*
  - *"We ingest data from heterogeneous sources, score opportunities across independent axes, verify founder claims to produce a Trust Score, and display the full chain-of-thought logic behind every recommendation."*

### **0:45 - 1:45 | Core Tech Stack & Architecture**
- **Action**: Briefly show the code structure or the architecture diagram from the README.
- **Talking Points**:
  - *"The stack is built on Python and Flask for a modular, high-speed backend, calling local Ollama models (Llama 3.2) for NLP task extraction. The frontend is a responsive Vanilla CSS single-page dashboard."*
  - *"Our backend executes a strict 4-stage pipeline: Sourcing, Screening, Diligence, and Decision. To prevent hallucinations, we use a hybrid approach: local LLMs perform text claim extraction, while pure Python rule-engines cross-reference facts against hard data."*

### **1:45 - 3:00 | Deep Dive into the Pillars (Live Demo)**
- **Action**: Click **Sourcing** in the sidebar. Highlight inbound vs. outbound candidates. Click **Screen** on a founder (e.g., Sofia Andersson / DeployKit).
- **Talking Points**:
  - ***Sourcing***: *"Here we have a unified inbox of inbound deck applications and outbound candidates found on GitHub. Notice the automated outreach templates generated when we activate an outbound founder."*
  - ***Multi-Axis Screening***: *"Sofia has been scored separately across Founder (based on repo commits/contributors), Market, and Idea-vs-Market. Critically, we never average these scores, showing investors the exact details of any disagreements."*
  - ***Thesis Engine***: *"We evaluate Sofia against our custom investment thesis. Investors can change sectors, stages, and check sizes in real-time under Thesis Config, and the pipeline filters profiles dynamically."*

### **3:00 - 4:15 | Trust Scoring & Agentic Traceability**
- **Action**: Navigate to the **Investment Memo** tab for the screened founder. Scroll down to show claim badges (`verified`, `contradicted`, `unverifiable`). Click **Show Reasoning** to open the CoT log.
- **Talking Points**:
  - ***Trust Score***: *"Every assertion the founder makes in their pitch deck is parsed by the LLM. Our Validator Agent checks this against GitHub data. For example, if a founder claims 50,000 active users, but their repo has only 3 stars, it is marked as `contradicted`."*
  - ***No Fabrication***: *"If a founder doesn't disclose financials or a cap table, the system explicitly flags `[Not Disclosed]` rather than hallucinating text."*
  - ***Traceability***: *"In the reasoning panel, you can see every single pipeline step. The system outputs which exact file, line, or repo signal was used to support a conclusion, providing complete transparency."*

### **4:15 - 5:00 | Outro & Summary**
- **Action**: Show the **Multi-Attribute Search** bar. Enter a query like *"technical founder, AI infra"* to show it filter profiles.
- **Talking Points**:
  - *"VC Brain demonstrates that venture capital can be data-driven, offline-safe, and transparent. Thank you for watching!"*

---

## 🚀 How to Run Locally

### 1. Prerequisites
- **Python 3.9+**
- **Ollama** (optional, for LLM claims extraction. If not running, VC Brain falls back to offline rule-based extraction).
  ```bash
  # Pull the default model
  ollama pull llama3.2:3b
  ollama serve
  ```

### 2. Setup & Installation
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Run the Dashboard
```bash
python app.py
```
Open `http://localhost:5000` in your web browser.

### 4. Running Automated Tests
VC Brain has a robust automated test suite covering all modules:
```bash
pytest tests/ -v
```

---

## 🏆 Hackathon Evaluation Criteria Mapping

- **Data Architecture (30%)**: Features robust ingestion of public GitHub REST endpoints and pitch deck texts, deduplicating records in a local persistent JSON memory.
- **Intelligent Analysis (25%)**: Runs claim validation comparing unstructured deck text assertions to structural signals, flagging anomalies automatically.
- **Investment Utility (30%)**: Produces investor-ready, structured memos with gap warnings, and outputs an interactive multi-attribute natural-language search bar.
- **User Experience (15%)**: Styled using a premium, clean dark-slate CSS grid. Notion-level approachability with Bloomberg-level analytical depth.
