# REASONS Canvas: Dark Theme UI Redesign — Stock Analyzer Dashboard
Date: 2026-07-05
Analysis: 2026-07-05-dark-theme-ui-redesign-analysis.md
Scope: FE-only

---

## R — Requirements

**Problem:** The current dashboard uses a blue-navy colour palette with an indigo accent, has no panel or card animations, renders section subheadings at 10px uppercase (invisible at a glance), and shows verbose inline setup instructions that clutter every form card.

**Goal:** Restyle the dashboard to a black-brown-silver palette with a copper accent, add panel fade-in and card stagger animations, a skeleton loader for auto-loading panels, upgrade subheading sizes, and strip all non-essential visible copy — without touching any backend route, Python module, or API contract.

**Definition of Done:**
- [ ] Given the dashboard is open on any panel, when the page renders, then the background is near-black, surface layers are warm dark brown, and all body text is warm silver
- [ ] Given a card or badge is displayed, when it appears, then borders and shadows use the brown palette and the copper accent replaces indigo throughout
- [ ] Given buy/sell/hold or yield curve status badges appear, when they render, then green/red/amber signal colours are unchanged and remain legible
- [ ] Given the user clicks a sidebar nav item, when the panel switches, then the new panel fades in over 150–200ms with a subtle upward slide
- [ ] Given the Market or Macro panel is navigated to for the first time, when the fetch is in-flight, then skeleton placeholder cards pulse gently instead of showing a plain spinner
- [ ] Given any panel renders data cards, when the cards appear, then each card staggers in with a 40–60ms delay between siblings
- [ ] Given the operating system has prefers-reduced-motion enabled, when any animation would play, then it is suppressed or instant
- [ ] Given any panel is open, when the panel renders with no data, then there are no visible developer instructions or multi-sentence placeholder paragraphs
- [ ] Given the Analysis panel is shown with no result, when the empty state renders, then it shows one concise prompt line only
- [ ] Given any panel is open, when a section subheading renders, then its font size is at least 15px and its font weight is 600 or higher
- [ ] Given the Market or Macro panel header h2 is rendered, when it appears, then its size is controlled by the panel-hd CSS class, not an inline style attribute

---

## E — Entities

### Frontend Artifacts

| Name | Type | Path | Responsibility |
|------|------|------|----------------|
| index.html — CSS design tokens block | Inline CSS section | templates/index.html lines 8–28 | Holds all 15 colour custom properties — these are the single source of truth for the entire palette |
| index.html — animation CSS block | Inline CSS section to add | templates/index.html after the existing keyframes | New keyframes for panel fade, skeleton pulse, and card stagger; prefers-reduced-motion block |
| index.html — .sec-title rule | Inline CSS rule | templates/index.html lines 188–198 | Current subheading class at 10px uppercase; needs size and case upgrade |
| index.html — .panel-hd rule | New inline CSS rule | templates/index.html after .sec-title | New class to replace the inline style attributes on Market and Macro panel h2 elements |
| index.html — Market panel header | Static HTML | templates/index.html line 533 | h2 with inline style that must be replaced by .panel-hd class |
| index.html — Macro panel header | Static HTML | templates/index.html line 553 | h2 with inline style that must be replaced by .panel-hd class |
| index.html — Analysis form hint paragraph | Static HTML | templates/index.html lines 511–515 | Verbose "News auto-fetched…" paragraph to remove |
| index.html — Scenario form hint paragraph | Static HTML | templates/index.html lines 646–650 | Verbose "Requires Ollama…" paragraph to remove |
| index.html — Alerts form intro paragraph | Static HTML | templates/index.html lines 670–675 | Verbose Telegram credential setup paragraph to remove |
| index.html — empty state st-desc elements | Static HTML and JS template strings | 4 locations across panels | Multi-sentence descriptions to trim to one line each |
| index.html — goPanel() function | Inline JS | templates/index.html lines 771–783 | Panel switch function; needs one requestAnimationFrame call to trigger fade class after display:block |

---

## A — Approach

**Pattern:** Single-file inline CSS and HTML edit with one small JS change — no build step, no new files, no dependencies.

**Strategy:** The entire change lives in one file. CSS edits are organised into five logical groups applied top-to-bottom: colour tokens, animation keyframes, subheading sizes, panel header class, and then the HTML cleanup pass for verbose copy. The JS change is a three-line addition to goPanel() — set display to block, request one animation frame, then add a fade-in class — avoiding the display-transition conflict that would silently suppress the animation.

**Scope In:**
- Replace all 15 CSS colour custom properties with the black-brown-silver palette
- Add fadePanel, skelPulse, and cardEnter keyframes
- Add prefers-reduced-motion media rule that disables all keyframe animations
- Update goPanel() to trigger fade class via requestAnimationFrame
- Add skeleton card HTML to the setLoad helper output for Market and Macro panels
- Add card stagger animation-delay nth-child rules for the metric card grids
- Upsize .sec-title from 10px to 15px, change text-transform from uppercase to none
- Add .panel-hd CSS class and replace inline style attributes on Market and Macro h2 elements
- Remove the Analysis form hint paragraph
- Remove the Scenario form hint paragraph
- Remove the Alerts Telegram setup paragraph
- Trim all four st-desc empty-state descriptions to one line

**Scope Out:**
- Light or dark mode toggle — the dashboard is always dark
- Changes to backend Python modules, app.py, or any API route
- Changes to the buy/sell/hold or severity colour tokens — green, red, amber, orange remain unchanged
- Changes to keyboard shortcut behaviour — Enter to analyse still works; only the visible hint text is removed
- Adding new panels, nav items, or data sources
- Changes to mobile bottom nav layout or breakpoints

---

## S — Structure

**Frontend file:** `Z:\claude\stock_analyzer\templates\index.html`

**New Files:** None — all changes are edits to the single existing file.

**Modified sections within index.html:**

- CSS design tokens block (lines 8–28) — replace all 15 colour values
- Animations block (after line 175, after existing @keyframes spin) — add fadePanel, skelPulse, cardEnter keyframes and prefers-reduced-motion block
- .sec-title rule (lines 188–198) — font-size 10px → 15px, remove text-transform uppercase
- After .sec-title — add new .panel-hd rule
- Market panel header (line 533) — remove inline style, add class="panel-hd"
- Macro panel header (line 553) — remove inline style, add class="panel-hd"
- Analysis form hint paragraph (lines 511–515) — remove entirely
- Scenario form hint paragraph (lines 646–650) — remove entirely
- Alerts intro paragraph (lines 670–675) — remove entirely
- Four st-desc elements — trim to one line each
- .panel CSS rule (line 100) — change display:none to opacity:0; add transition; .panel.active sets opacity:1
- goPanel() function (lines 771–783) — add requestAnimationFrame fade class trigger
- setLoad() helper (line 822) — add skeleton card HTML output for data panels

---

## O — Operations

1. Replace the 15 CSS colour custom properties in the :root block with the black-brown-silver palette: near-black background, dark charcoal-brown surface layers, warm silver text, brown borders, and a copper accent replacing indigo

2. Add the animation CSS block after the existing @keyframes spin rule: fadePanel keyframe (opacity 0 to 1, translateY 6px to 0, duration 180ms ease-out), skelPulse keyframe (background gradient shimmer, 1.4s infinite), cardEnter keyframe (opacity 0 to 1 with translateY 4px, 200ms ease-out), and nth-child stagger rules applying animation-delay increments of 50ms to the first six siblings within .g4 and .g5 grid containers

3. Add the prefers-reduced-motion media rule that sets animation-duration to 0.01ms and transition-duration to 0.01ms for all elements

4. Update the .sec-title CSS rule: change font-size from 10px to 15px, remove text-transform uppercase, set letter-spacing to 0, keep font-weight 600

5. Add the .panel-hd CSS class: font-size 18px, font-weight 700, color var(--tx), line-height 1.2

6. In the Market panel static HTML, replace the inline style attribute on the h2 element with class="panel-hd" — remove the subtitle paragraph (keep it, it is not classified as verbose)

7. In the Macro panel static HTML, replace the inline style attribute on the h2 element with class="panel-hd"

8. Update the .panel CSS rule and .panel.active rule to use opacity-based visibility: .panel gets display:none with opacity 0; .panel.active gets display:block with a fadePanel animation applied; this is driven by the JS change in the next step

9. Update goPanel() to trigger the panel animation correctly: after setting the panel to active, use requestAnimationFrame to add a visible class one frame later so the CSS transition fires — this avoids the display:none transition-blocking problem

10. Update the setLoad() helper to emit skeleton card HTML instead of a plain spinner: three placeholder .sk-card div elements with a pulsing .skeleton background, used when loading Market and Macro data

11. Remove the Analysis panel form hint paragraph (the "News auto-fetched…" text), remove the Scenario panel form hint paragraph (the "Requires Ollama…" text), and remove the Alerts panel Telegram credential setup paragraph

12. Trim the four empty-state st-desc elements: Analysis ("Enter a ticker to analyze"), Portfolio ("Add 2+ tickers to optimize"), Scenario ("Describe an event to simulate"), and Alerts history ("No alerts sent yet") — each to one line only

---

## N — Norms

### Frontend Norms

- All CSS is written as inline styles within the single templates/index.html file — no separate CSS file exists or should be created
- Use CSS custom properties for all colour and spacing values — never hardcode hex values in component rules
- All animation keyframes must have a corresponding prefers-reduced-motion override
- Vanilla JS only — no libraries, no frameworks, no npm dependencies
- All interactive elements must remain keyboard accessible — do not remove aria-label attributes
- Do not use alert(), confirm(), or prompt() — all user feedback goes to inline DOM elements
- Empty state messages must guide the user toward an action in one line — no explanatory paragraphs
- The fetchJSON helper must remain intact — all API calls route through it

---

## S — Safeguards

### Frontend Safeguards

- Do not touch any Python file, app.py, or any file outside templates/index.html
- Do not change the green, red, amber, or orange colour tokens — buy/sell/hold signals depend on them
- Do not remove aria-label attributes, skip-to-content link, or any :focus-visible rule
- Do not change API endpoint URLs, HTTP methods, or request payload shapes
- Do not remove keyboard shortcut event listeners (Enter to analyze, Ctrl+Enter for scenario)
- The display:none → display:block panel transition must use requestAnimationFrame to avoid the CSS transition suppression bug — do not use a CSS-only approach with visibility:hidden as it will break the layout
- Test that all six panels still load their data correctly after the animation change
- Skeleton cards must not replace actual data — they appear only while the fetch is in-flight, replaced by real content on success

---

## Change Log

(empty — first version)
