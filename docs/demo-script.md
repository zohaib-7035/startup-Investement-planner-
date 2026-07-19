# VC Brain — Live Demo Script

**Total budget: ≤ 5 minutes (300 seconds)**
**Audience: Hackathon judges evaluating agentic traceability, trust scoring, and investment utility**

---

## Setup (before the demo — 60 s)

1. Start the server: `python app.py`
2. Confirm status line shows: `Ollama (llama3.2:3b): OK — ready` (or note offline mode)
3. Open `http://localhost:5000` in a browser
4. The dashboard opens on the Stock Analysis panel — this is fine, we will navigate from here

**Offline fallback:** If Ollama is not running, claim extraction uses a regex fallback. The Trust Score badges still work (signal-based, rule-based). Mention this to judges: "The system degrades gracefully — no single point of failure."

---

## Moment 1 — Outbound sourcing chip (30 s)

**Goal:** Show that VC Brain sources founders proactively from GitHub, not just from inbound applications.

1. Click **Sourcing** in the sidebar (🔍 icon) or bottom nav
2. The list of 19 synthetic founders loads automatically
3. Point to **Sofia Andersson / DeployKit**:
   - Her row shows a blue **`outbound`** chip — she was discovered by a GitHub scan, not an inbound application
   - Other rows show grey **`inbound`** chips for founders who applied directly
4. Say: "Inbound and outbound deals in a single unified view — the sourcing funnel starts here."

**Offline fallback:** Founders load from `data/sample_founders.json` — no network required.

---

## Moment 2 — Three axes, never combined (60 s)

**Goal:** Demonstrate that VC Brain scores founders on three independent axes — never averaged into a single number.

1. On the Sourcing panel, click **Screen →** next to **Sofia Andersson / DeployKit**
2. The app navigates to the **Screening** panel and runs the full pipeline
3. Point to the three axis cards:
   - **Founder axis** — score + trend arrow (▲/▼/→) + evidence bullets citing actual signals
   - **Market axis** — separate score, separate evidence (sector outlook)
   - **Idea vs. Market axis** — separate score for product-market fit assessment
4. Say: "A first-time founder in a hot market with a weak product is not the same as a repeat founder in a cold market — these axes must stay separate. We never produce a single combined score."
5. Note the **Thesis: PASS** or **FAIL** label above the axes — shows whether this deal fits the configured investment thesis

**Offline fallback:** All three axes are computed by rule-based signal math in `scoring_engine.py` — no LLM required.

---

## Moment 3 — Contradicted claim badge (60 s)

**Goal:** Show that VC Brain catches traction fabrication with a `contradicted` badge.

1. Go back to **Sourcing** (sidebar)
2. Click **Screen →** next to **Priya Venkatesan / FinAI Labs**
3. Wait for screening to complete, then click **View Memo →** (or navigate to **Memo** in sidebar)
4. In the Claims & Trust Scores section, find the claim about user traction:
   - The claim referencing ~48,000 users will show a red **`✗ contradicted`** badge
   - This fires because `total_stars=92` in her GitHub signals is inconsistent with 48,000 active users — the Trust Scorer flags the contradiction
5. Say: "The system doesn't just pass through what founders claim — it cross-references each claim against available GitHub signals and flags contradictions automatically."

**Alternative:** If time is short, use **Devon Marsh / TractionMax** — the contradiction is more dramatic (200,000 claimed users vs. 3 total stars).

**Offline fallback:** `verify_claim()` is fully rule-based — no Ollama needed for contradiction detection.

---

## Moment 4 — Not Disclosed flag (30 s)

**Goal:** Show that VC Brain never fabricates data for missing sections.

1. Stay on the **Memo** panel for the current founder
2. Scroll to the **Financials** or **Cap Table** section
3. The section shows a yellow **`not disclosed`** badge instead of invented numbers
4. Say: "Pitch decks often omit cap table details. Most tools either hallucinate placeholder numbers or leave the section blank. VC Brain flags the gap explicitly — the investor knows exactly what information is missing, and why."

**Offline fallback:** Gap flagging is hardcoded in `memo_generator.py` — independent of LLM.

---

## Moment 5 — Reasoning / traceability panel (60 s)

**Goal:** Demonstrate agentic traceability — every conclusion cites the exact data point that drove it.

1. Go back to the **Screening** panel (navbar or re-run screening for any founder)
2. Scroll to the bottom of the screening results
3. Click **Show reasoning (N steps)** to expand the `<details>` panel
4. Walk through 2-3 steps with judges:
   - An axis step: *"Founder axis: score 68/100, improving ▲ — data point: commit_frequency=11 → bullish"*
   - A risk flag step: *"RiskScanner: risk flagged: claim_contradiction at high — data point: total_stars=3 contradicts 200k user claim"*
   - A claim step: *"TrustScorer: claim contradicted — data_point: total_stars=3 contradicts 200k user claim — high risk of fabrication"*
5. Say: "This is agentic traceability — not an explanation generated after the fact, but a live log of which signal, in which module, drove which conclusion. Every step is auditable."

**Offline fallback:** `reasoning_log.py` is fully offline — it consumes structured pipeline outputs, no LLM required.

---

## Closing line (10 s)

> "VC Brain gives you the sourcing breadth of a scout network, the analytical depth of a due-diligence analyst, and a reasoning trail that makes every recommendation auditable — all running locally, no paid APIs."

---

## Quick-Reference Panel Navigation

| Goal | Sidebar icon | Keyboard shortcut |
|------|-------------|-------------------|
| Sourcing list | 🔍 | Click sidebar |
| Run screening | Screen → button | — |
| View memo | 📋 or View Memo → | — |
| Thesis config | ⚙ | Click sidebar |
| Expand reasoning | Show reasoning ▶ | Enter / Space on `<details>` |

---

## If Something Breaks

| Problem | Recovery |
|---------|---------|
| `api/screen/<idx>` returns error | Check Flask console — usually a missing `data/` dependency; run `pytest tests/` to confirm state |
| Ollama not running | Claim extraction falls back to regex; screening still works |
| Founders list empty | Click ↻ Refresh on Sourcing panel; verify `data/sample_founders.json` exists |
| Memo shows no claims | LLM offline + no pitch text in profile → normal for GitHub-only outbound profiles |
