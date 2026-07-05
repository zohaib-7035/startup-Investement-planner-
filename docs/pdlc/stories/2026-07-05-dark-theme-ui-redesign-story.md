# User Story: Dark Theme UI Redesign — Stock Analyzer Dashboard
Date: 2026-07-05
Source: Pasted text

---

## Story 1: Dark Theme Color Scheme

**As a** platform admin (stock analyzer user),
**I want** the entire dashboard restyled with a dark theme using black, dark brown, and silver tones,
**So that** the interface is easier on the eyes during extended analysis sessions and looks professional.

### Scope In
- Apply new CSS design tokens: near-black background, dark brown surface layers, silver/warm-gray text and borders
- Update all 6 panels (Analysis, Market, Macro, Portfolio, Scenario, Alerts) with the new palette
- Update sidebar, topbar, cards, tables, and form inputs
- Ensure sufficient contrast for all text on colored backgrounds (WCAG AA minimum)

### Scope Out
- Light/dark mode toggle (always dark — no toggle required for this story)
- Changes to backend API routes or data logic
- Mobile-only layout changes (responsive behavior preserved as-is)

### Acceptance Criteria
- Given the dashboard is open, when any panel is displayed, then the background is a near-black tone, surfaces use dark brown/charcoal layers, and text is silver or warm-gray
- Given a card or data cell is rendered, when it is visible, then its border and shadow use the new silver/muted palette without the existing indigo (`#6366f1`) accent dominating
- Given a status badge (buy/sell/hold, NORMAL/INVERTED, etc.) is displayed, when it appears, then it is legible with sufficient contrast against the dark brown surface

### Definition of Done
- [ ] New CSS design tokens defined as CSS custom properties (`--bg`, `--s1`, `--s2`, `--text`, `--muted`, `--border`)
- [ ] All 6 panels styled consistently with the new palette
- [ ] No existing data binding or API wiring broken
- [ ] Visually reviewed in Chrome at 1440px width

---

## Story 2: UI Animations

**As a** platform admin (stock analyzer user),
**I want** subtle animations on key UI transitions and data-load events,
**So that** the dashboard feels responsive and premium rather than static.

### Scope In
- Panel transition animation when switching between sidebar items (fade or slide)
- Card entrance animation when a panel first loads its data (stagger fade-in)
- Loading skeleton pulse animation while API data is fetching
- Metric value flip/count-up animation when numbers update (optional: only if performant)

### Scope Out
- Continuous background animations or particle effects (distracting for data-dense screens)
- Animations on every DOM update (only meaningful entry/transition moments)
- CSS animation library dependencies (use native CSS keyframes)

### Acceptance Criteria
- Given the user clicks a sidebar nav item, when the panel switches, then the new panel fades in over 150–200ms
- Given a panel is loading data, when the fetch is in-flight, then skeleton placeholder cards pulse gently
- Given data arrives and cards render, when they appear, then each card staggers in with a 40–60ms delay between items
- Given `prefers-reduced-motion` is set in the OS, when any animation would play, then it is suppressed or reduced to an instant transition

### Definition of Done
- [ ] Panel switch fade implemented with CSS `transition` or `@keyframes`
- [ ] Skeleton loader pulse implemented for all 6 panels
- [ ] Card stagger entrance implemented with `animation-delay` increments
- [ ] `@media (prefers-reduced-motion: reduce)` rule present and disables all keyframe animations
- [ ] No jank at 60 fps on a standard laptop (verified in DevTools Performance tab)

---

## Story 3: Production-Level Text Cleanup

**As a** platform admin (stock analyzer user),
**I want** all non-essential labels, redundant helper text, and placeholder copy removed from the UI,
**So that** the dashboard looks clean and production-ready rather than prototype-quality.

### Scope In
- Remove inline "how to use" instructions and debug-helper text visible in the rendered UI
- Remove redundant section labels that duplicate what the panel heading already states
- Remove placeholder copy such as "No data yet — run an analysis first" where a clean empty state suffices
- Keep empty-state messages only where they guide the user to take an explicit action (e.g. "Enter a ticker above to analyze")

### Scope Out
- Changes to API error messages returned by the backend
- Removal of WCAG labels or `aria-*` attributes (accessibility must not regress)
- Changes to tooltips or help text that are hidden by default (only remove visible clutter)

### Acceptance Criteria
- Given the dashboard is open on any panel, when the panel renders with no data, then there are no visible strings that read like developer notes or placeholder instructions
- Given the Analysis panel is shown, when no ticker has been entered, then the empty state is a single concise prompt, not a multi-sentence explanation
- Given the Alerts panel is shown, when no alerts exist, then the empty state is a single line, not a paragraph

### Definition of Done
- [ ] All 6 panels reviewed and verbose inline help text removed or condensed
- [ ] Empty-state messages reduced to one line maximum per panel
- [ ] No visible `TODO`, `placeholder`, or draft copy remains in the rendered HTML

---

## Story 4: Bold and Larger Panel Subheadings

**As a** platform admin (stock analyzer user),
**I want** all subheadings within each panel to be visually prominent — larger and bold,
**So that** I can scan panel sections at a glance without reading fine print.

### Scope In
- All `<h3>` and `<h4>` elements within panel content areas
- Section dividers inside panels (e.g. "Yield Curve", "Treasury Yields", "Economic Indicators" within the Macro panel)
- Card group labels within the Market and Portfolio panels

### Scope Out
- Top-level panel titles in the topbar (already styled by the topbar component)
- Table column headers (use existing `<th>` styling)
- Form field labels within the Analysis/Scenario input forms

### Acceptance Criteria
- Given any panel is open, when a subheading (`<h3>` or `<h4>`) is visible, then its `font-size` is at least 1rem larger than body text and its `font-weight` is 600 or 700
- Given the Macro panel is shown, when the "Treasury Yields" and "Economic Indicators" section titles appear, then they are visually distinct from the card labels beneath them
- Given any panel is viewed on a 1280px viewport, when subheadings are rendered, then they do not overflow or wrap awkwardly

### Definition of Done
- [ ] CSS rules for `.panel-content h3` and `.panel-content h4` set `font-size` and `font-weight` explicitly
- [ ] All 6 panels verified visually — no subheading is the same size as body text
- [ ] No existing layout breaks due to larger subheading line height
