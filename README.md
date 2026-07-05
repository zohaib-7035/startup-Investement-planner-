# AI Stock Intelligence Platform

A fully local, free-to-run stock analysis platform powered by a multi-agent AI pipeline. No paid APIs — everything runs on your machine using Ollama (local LLM), VADER (offline sentiment), yfinance (free market data), and FRED (free economic data).

![Dark Theme UI](https://img.shields.io/badge/UI-Dark%20Theme-b8966a?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-2.3-lightgrey?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Features

- 8 fully functional pages in a single-page dark-theme dashboard
- Multi-agent pipeline: sentiment, signals, risk, macro, screener, meta-decision all run in parallel
- 100% local — no OpenAI, no Anthropic, no paid APIs
- 532+ unit tests across 21 backend modules

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.9 |
| Ollama | Latest |
| Ollama model | `llama3.2:3b` |

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/stock-analyzer.git
cd stock-analyzer
```

**2. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**3. Install and start Ollama**

Download from [https://ollama.com](https://ollama.com), then run:
```bash
ollama serve
ollama pull llama3.2:3b
```

**4. Run the server**

Windows (recommended):
```bash
run_server.bat
```

Or directly:
```bash
python app.py
```

**5. Open in browser**
```
http://localhost:5000
```

---

## Environment Variables

All have sensible defaults — you do not need to set any of these to get started.

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `llama3.2:3b` | LLM model to use |
| `FLASK_PORT` | `5000` | Port Flask listens on |
| `FLASK_HOST` | `0.0.0.0` | Host Flask binds to |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `USE_TF` | `0` | Disable TensorFlow (keep 0) |
| `USE_TORCH` | `1` | Enable PyTorch for embeddings |

---

## Pages

### 1. Stock Analysis
**How to use:**
1. Type a ticker symbol in the search box (e.g. `AAPL`, `TSLA`, `MSFT`)
2. Click **Analyze**
3. Wait ~10–30 seconds while the 6-agent pipeline runs in parallel

**What you get:**
- Buy / Sell / Hold recommendation with confidence score
- Price history chart (SVG, no libraries)
- Sentiment analysis of recent news (VADER, offline)
- Technical signals (RSI, MACD, Bollinger Bands, moving averages)
- Fundamental data (P/E ratio, EPS, market cap, revenue)
- Risk metrics (Value-at-Risk, volatility)
- Macro context (yield curve, inflation, unemployment)

---

### 2. Market Snapshot
**How to use:**
1. Click **Refresh** to load current market data
2. No input needed — shows major indices automatically

**What you get:**
- Live prices and daily change for S&P 500, Nasdaq, Dow Jones, Russell 2000
- Fear & Greed style market breadth indicator
- Top gainers and losers of the day
- Sector performance overview

---

### 3. Macro Indicators
**How to use:**
1. Click **Load Macro Data**
2. Data loads automatically from FRED (Federal Reserve Economic Data — free)

**What you get:**
- US GDP growth rate
- CPI inflation rate
- Federal Funds Rate
- Unemployment rate
- 10-year Treasury yield
- Yield curve (2Y vs 10Y spread) — inverted curve signals recession risk

---

### 4. Portfolio Optimizer
**How to use:**
1. Type ticker symbols one by one, pressing **Enter** or **comma** after each (e.g. `AAPL` → Enter → `MSFT` → Enter → `GOOGL` → Enter)
2. Set your **Risk Tolerance** using the slider (0 = Conservative, 1 = Aggressive)
3. Choose your **Horizon** (1, 2, 3, or 5 years of historical data)
4. Click **Optimize Portfolio**

**What you get:**
- Optimal allocation percentages for each ticker (Markowitz mean-variance optimization)
- Expected annual return
- Portfolio volatility
- Sharpe ratio

**Tips:**
- Add at least 2 tickers (required)
- Add 4–6 tickers for meaningful diversification
- Conservative setting minimizes volatility; Aggressive maximizes return

---

### 5. Scenario Simulation
**How to use:**
1. Describe a macroeconomic or geopolitical event in the text box (e.g. *"Federal Reserve raises interest rates by 100 basis points"*)
2. Optionally use one of the preset example buttons
3. Enter a ticker to simulate impact on (e.g. `AAPL`)
4. Click **Simulate**

**What you get:**
- Predicted price impact (% change) on the ticker
- Sector-level impact breakdown
- Confidence score
- Reasoning from the LLM

**Note:** Requires Ollama running. Simulation takes 10–30 seconds.

---

### 6. Alerts
**How to use:**
1. Enter a ticker symbol
2. Set a **price threshold** (above or below)
3. Set an optional **signal condition** (RSI overbought, MACD crossover, etc.)
4. Click **Set Alert**

**What you get:**
- Alerts are stored in-session and checked against live prices
- Triggered alerts show in the notification panel
- Alerts can be cleared individually or all at once

---

### 7. Backtesting
**How to use:**
1. Enter a ticker (e.g. `AAPL`)
2. Set a **Start Date** and **End Date** for the backtest window
3. Add trading signals — for each signal:
   - Enter a **date** (must be within your start/end range, format: MM/DD/YYYY)
   - Select **BUY** or **SELL**
   - Click **Add Signal**
4. First signal must be a **BUY**
5. Click **Run Backtest**

**What you get:**
- Trade-by-trade table (entry date, exit date, entry price, exit price, P&L)
- Portfolio value chart over time
- Total return and final portfolio value

**Example:**
- Ticker: `AAPL`
- Start: `01/01/2024`, End: `12/31/2024`
- Signal 1: `03/15/2024` → BUY
- Signal 2: `07/01/2024` → SELL

---

### 8. Knowledge Graph
**How to use:**
1. Paste any financial news article, earnings report, or description of company relationships into the **Entity / News Text** box
2. Optionally enter a **Disrupted Entity** (a company name) to highlight its impact connections
3. Click **Extract Graph**

**What you get:**
- Visual graph showing entity nodes (companies, regulators, etc.) connected by labeled relationship arrows
- Relationship Triples table listing every Subject → Relation → Object extracted
- Confidence scores per relationship

**Example text:**
> *Apple acquired Intel's smartphone modem business. TSMC supplies chips to Apple and NVIDIA. The Federal Reserve raised interest rates, impacting tech stocks.*

**Note:** Requires Ollama running. Extraction takes 15–40 seconds depending on text length.

---

## Project Structure

```
stock_analyzer/
├── app.py                  # Flask application, all API routes
├── run_server.bat          # Windows startup script (recommended)
├── requirements.txt
├── templates/
│   └── index.html          # Entire frontend (single file, vanilla JS)
└── data/                   # Backend modules (one file per agent)
    ├── stock.py            # yfinance price + fundamentals
    ├── sentiment.py        # VADER news sentiment
    ├── signals.py          # RSI, MACD, Bollinger Bands
    ├── screener.py         # Buy/Sell/Hold rules engine
    ├── risk.py             # VaR, volatility, risk metrics
    ├── macro_data.py       # FRED economic indicators
    ├── market_data.py      # Indices, sectors, gainers/losers
    ├── scenario.py         # Ollama scenario simulation
    ├── portfolio.py        # Markowitz optimization (scipy)
    ├── backtester.py       # Signal-driven backtesting engine
    ├── knowledge_graph.py  # Ollama entity extraction
    ├── graph_reasoning.py  # BFS impact analysis
    ├── meta_agent.py       # Aggregates all agent signals
    ├── parallel_runner.py  # Concurrent agent execution
    ├── notifier.py         # Alert management
    ├── report.py           # Report generation
    └── ...                 # RAG modules (vector_store, edgar_client, etc.)
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

532+ tests across 21 modules. All tests use mocks — no live API calls required.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.9 + Flask |
| Frontend | Vanilla JS + HTML/CSS (no frameworks) |
| LLM | Ollama (`llama3.2:3b`) — local, free |
| Sentiment | VADER — offline, no API |
| Stock data | yfinance — free |
| Economic data | FRED API — free |
| Portfolio math | NumPy + SciPy |
| Vector store | ChromaDB + sentence-transformers |

---

## License

MIT
