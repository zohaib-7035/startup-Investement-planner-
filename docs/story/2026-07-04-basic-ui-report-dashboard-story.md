# User Story: Basic UI Report Dashboard
Date: 2026-07-04
Source: Pasted text

---

## Story 21: Generate Minimal HTML Report from Pipeline Outputs

**As a** financial analyst using the AI Stock Intelligence Platform,
**I want** a Python function that renders all pipeline outputs into a self-contained HTML report,
**So that** I can review company recommendation, confidence score, technical signals, fundamentals, sentiment, risk level, portfolio allocation, and timestamp in a single readable document without running a web server.

### Scope In
- New module `data/report.py` with one public function: `render_report(data)`
- Input: a single dict with 9 keys — `company_name`, `recommendation`, `confidence_score`, `technical_signals`, `fundamentals`, `sentiment`, `risk_level`, `portfolio_allocation`, `timestamp`
- Output: a self-contained HTML string (inline CSS, no external dependencies, no JavaScript)
- Graceful handling of missing or None fields — render "N/A" placeholder per field
- Fallback HTML page returned for empty dict or None input — no exception raised
- MVP visual quality: labelled sections, readable font, colour-coded recommendation badge (BUY=green, SELL=red, HOLD=amber)

### Scope Out
- No live/interactive dashboard (no Flask, no FastAPI, no WebSockets)
- No PDF or CSV export
- No chart or graph rendering (no matplotlib, no chart.js)
- No real-time data refresh or polling
- No authentication or multi-user session handling
- No Markdown output variant (HTML only for MVP)
- No integration with a running HTTP server

### Acceptance Criteria
- Given a fully populated data dict, when `render_report(data)` is called, then it returns a non-empty HTML string that contains all 9 field values
- Given the returned HTML string, when saved to a `.html` file and opened in a browser, then each section is visually distinct, labelled, and readable without a framework
- Given a data dict where one or more fields are `None`, when `render_report(data)` is called, then those fields render as "N/A" and all other fields render normally
- Given `None` or an empty dict `{}` as input, when `render_report(data)` is called, then it returns a minimal fallback HTML page with a "No data available" message and does not raise an exception
- Given a `confidence_score` float between 0.0 and 1.0, when rendered, then it is displayed as a percentage (e.g. `0.85` → `85%`)
- Given a `recommendation` value of "BUY", "SELL", or "HOLD", when rendered, then the badge background is green, red, or amber respectively
- Given a `portfolio_allocation` dict (ticker → weight), when rendered, then each ticker and its weight percentage are listed

### Definition of Done
- [ ] `data/report.py` implemented with `render_report(data)` following module-per-concern pattern
- [ ] Exception boundary: outer `try/except` — never raises to caller
- [ ] `tests/test_report.py` written with all tests Strong (no Meaningless, no Weak)
- [ ] HTML output manually verified in a browser for MVP readability
- [ ] All 399 existing tests still pass after adding the new module
- [ ] Test review passes: Recommendation: Ready

---
