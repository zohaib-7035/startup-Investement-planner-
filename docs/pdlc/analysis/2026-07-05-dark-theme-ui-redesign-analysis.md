# Analysis: Dark Theme UI Redesign — Stock Analyzer Dashboard
Date: 2026-07-05
Story: 2026-07-05-dark-theme-ui-redesign-story.md
Scope: FE-only
Repos scanned: Z:\claude\stock_analyzer (local)
Figma: none

---

## Project Fingerprint

This is a Python Flask application with a single-file frontend: `templates/index.html` (~1472 lines of inline CSS + HTML + vanilla JS). No build system, no npm, no SCSS preprocessing — all styles are CSS custom properties written directly. The color system uses a blue-navy palette (`--bg: #080d18`, `--accent: #6366f1` indigo). Panel switching is handled by `goPanel()` toggling `.active` (which maps to `display:block`). The only animation in the file is a spinner `@keyframes spin`. Section subheadings use `.sec-title` (10px uppercase small caps).

---

## Domain Concepts

### Existing in Codebase
| Concept | Location | Notes |
|---------|----------|-------|
| CSS design tokens | `index.html` lines 8–28 | 15 custom properties; all colors are blue-navy today |
| `.sec-title` subheading class | `index.html` lines 188–198 | 10px uppercase — the main subheading class used across all JS-rendered sections |
| `@keyframes spin` | `index.html` line 175 | Only existing animation; used by `.spinner` |
| `goPanel()` | `index.html` lines 771–783 | Switches panels via `classList.toggle('active')`; no CSS transition |
| `.st-load` / `.st-empty` state blocks | `index.html` lines 166–171 | Loading state uses spinner; no skeleton pulse exists |
| Panel header `<h2>` elements | Market panel line 533, Macro panel line 553 | Inline `style="font-size:16px;font-weight:700"` — not class-driven |
| Inline hint paragraphs | Analysis line 511, Scenario line 646, Alerts line 670 | Verbose setup/keyboard instructions visible inside form cards |
| Empty-state `st-desc` elements | Analysis line 523, Portfolio line 612, Scenario line 657, Alerts line 715 | Multi-sentence descriptions; some duplicate what the panel already conveys |

### Missing or Needs to Be Added
| Concept | Type | Notes |
|---------|------|-------|
| Black-brown-silver design tokens | CSS custom properties | Replace all 15 current blue-navy tokens |
| Panel fade-in animation | `@keyframes` + `.panel.active` rule | `goPanel()` needs to trigger opacity transition after display:block |
| Skeleton loader pulse | `@keyframes` + `.skeleton` class | Replace solid spinner with pulsing placeholder cards in Market and Macro panels |
| Card stagger entrance | CSS `animation-delay` on nth-child | Stagger 40–60ms between sibling `.mc` cards |
| `prefers-reduced-motion` media block | `@media` rule | Must disable all keyframe animations |
| `.sec-title` size upgrade | CSS rule edit | Increase from 10px to 15–16px, remove forced uppercase, keep weight 600+ |
| `.panel-hd` class for panel `<h2>` headings | New CSS class + HTML edit | Replace inline `style=` on Market and Macro `<h2>` elements |

---

## Strategic Approach

All four stories target a single file (`templates/index.html`), so the entire change is one structured CSS + HTML edit with no backend impact. The approach: (1) swap the 15 design tokens at the top of `:root` to shift from blue-navy to black-brown-silver; (2) add `@keyframes fadePanel` and update `goPanel()` to add a `.fade-in` class one animation frame after `display:block`; (3) add skeleton loader CSS and use it in the `setLoad()` helper for Market and Macro panels; (4) upsize `.sec-title` and extract the Market/Macro inline `<h2>` styles to a `.panel-hd` class; (5) strip the three verbose inline hint paragraphs and trim `st-desc` copy to one line each.

---

## Key Design Decisions

- **Black-brown-silver palette**: `--bg: #0a0807`, `--s1: #12100d`, `--s2: #1a1510`, `--s3: #221b14`, `--b1: #2e2218`, `--b2: #3d2e1e`, `--tx: #d8cfc4`, `--muted: #8a7a6a`, `--dim: #4a3c30`, `--accent: #b8966a` (copper/bronze replacing indigo)
- **Panel transition via CSS class, not `display`**: `goPanel()` sets `display:block` then adds `.fade-in` on the next animation frame; `@keyframes fadePanel` handles opacity + translateY(6px → 0)
- **Skeleton loader replaces spinner for auto-load panels**: Market and Macro load on nav; skeleton cards look more premium and feel faster than a spinner
- **`.sec-title` stays as a class** (not converted to `h3`): it is generated inside JS template strings — a CSS change is the minimal, zero-risk path
- **Green/red/amber buy-sell signals are not changed**: these are financial signal colors that must remain standard

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| `display:none` → `display:block` CSS transition doesn't animate | High | Transition on `opacity` requires `display:block` first; add `.fade-in` class one rAF later |
| Brown/copper accent contrast on dark background | Medium | Test `#b8966a` on `#12100d`; if contrast < 4.5:1 lighten to `#c8a878` |
| Skeleton pulse color too close to background | Low | Skeleton gradient range `--s3` → `--b1`; verify visually distinct |
| Inline `style=` on Market/Macro `<h2>` overrides class CSS | Medium | Must remove inline styles; replace with `.panel-hd` class |
| Removing Telegram setup paragraph loses only onboarding hint | Low | Requirement is in README; safe to remove from UI |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Background near-black, surfaces dark brown, text silver | Needs work | Tokens exist but are blue-navy; swapping 15 values covers this |
| Borders and shadows use silver/muted palette, not indigo-dominant | Needs work | `--b1`, `--b2`, `--accent` all need palette shift |
| Status badges legible on dark brown surfaces | Supported | Green/red/amber badge colors are independent; no change needed |
| Panel switches fade over 150–200ms | Needs work | `goPanel()` has no animation; add `fadePanel` keyframe + rAF class toggle |
| Skeleton pulse while fetch is in-flight | Needs work | Only spinner exists; add skeleton cards for Market and Macro panels |
| Cards stagger in 40–60ms | Needs work | No stagger exists; add `animation-delay` nth-child rules on `.mc` |
| `prefers-reduced-motion` suppresses animations | Needs work | No such rule in the file |
| No developer-note text in rendered UI | Needs work | 3 inline hint paragraphs + 4 verbose empty-state descriptions to trim |
| Analysis empty state is one concise prompt | Needs work | Trim "Enter a ticker and click Run Analysis to start the 6-agent pipeline" |
| Alerts empty state is one line | Supported | Already one line |
| Subheadings font-size ≥ 1rem larger than body, weight 600+ | Needs work | `.sec-title` is 10px; Market/Macro `<h2>` inline style must move to CSS |
| No subheading overflow at 1280px | Supported | Grid layout handles it; larger text won't cause overflow |

---

## Dependencies

`templates/index.html` only — no backend files, `app.py`, Python modules, or separate asset files are affected.
