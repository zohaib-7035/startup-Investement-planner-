# User Story: Advanced Signals Agent
Date: 2026-07-04
Source: Pasted text

---

## Story 22: Generate Advanced Trading Signal from ADX, ATR, Momentum, and Volume

**As a** financial analyst using the AI Stock Intelligence Platform,
**I want** a rule-based signal engine that evaluates ADX trend strength, ATR volatility, price momentum, and volume ratio together,
**So that** I can receive a BUY, SELL, HOLD, or WATCHLIST recommendation with a confidence score and human-readable reasoning without relying on an LLM call.

### Scope In
- New module `data/signals.py` with one public function: `generate_advanced_signal(adx, atr, momentum, volume_ratio)`
- Four input parameters: `adx` (float, 0–100), `atr` (float, ≥0), `momentum` (float, any value), `volume_ratio` (float, ≥0)
- Four possible actions: `"BUY"`, `"SELL"`, `"HOLD"`, `"WATCHLIST"` (WATCHLIST is new — not in `screener.py`)
- Return dict with three keys: `{action, confidence, reason}` — same schema as `generate_recommendation`
- Ordered rule set (first match wins):
  1. **BUY** — ADX > 25 AND momentum > 0 AND volume_ratio >= 1.5 (strong trend with positive momentum and volume confirmation)
  2. **SELL** — ADX > 25 AND momentum < 0 AND volume_ratio >= 1.5 (strong trend with negative momentum and volume confirmation)
  3. **WATCHLIST** — ADX >= 20 AND ADX <= 25 (emerging trend, not yet strong enough for BUY/SELL — watch for confirmation)
  4. **HOLD** — all other cases (no clear signal)
- ATR used as a confidence modifier: high ATR (> 5.0) reduces confidence by 10% to reflect elevated volatility risk
- Module-level `_CONFIDENCE_MAP`: `{"BUY": 0.85, "SELL": 0.75, "WATCHLIST": 0.55, "HOLD": 0.40}`
- All input validation via private `_safe_indicator` helper — invalid inputs (None, non-numeric, negative ADX/ATR/volume_ratio, ADX > 100, infinity/NaN) return invalid-input fallback with `confidence: 0.0`
- Pure Python stdlib only — no LLM, no HTTP, no numpy
- Never raises

### Scope Out
- No integration with live market data feeds — function accepts pre-computed indicator values only
- No RSI or EPS-based rules from `screener.py` — this is a separate, independent signal module
- No position sizing or stop-loss calculation (ATR is used only for confidence adjustment, not sizing)
- No multi-timeframe analysis
- No combination or blending with `generate_recommendation` output — that is the caller's responsibility
- No `pe_ratio` or fundamental inputs — technical signals only

### Acceptance Criteria
- Given `adx=38, atr=4.2, momentum=0.15, volume_ratio=1.8`, when `generate_advanced_signal(...)` is called, then it returns `{action: "BUY", confidence: 0.85, reason: <non-empty string>}`
- Given `adx=32, atr=3.1, momentum=-0.12, volume_ratio=1.6`, when called, then it returns `action: "SELL"` with `confidence: 0.75`
- Given `adx=22, atr=2.0, momentum=0.05, volume_ratio=1.1`, when called, then it returns `action: "WATCHLIST"` with `confidence: 0.55`
- Given `adx=15, atr=1.5, momentum=0.02, volume_ratio=0.9`, when called, then it returns `action: "HOLD"` with `confidence: 0.40`
- Given `adx=38, atr=6.5, momentum=0.15, volume_ratio=1.8`, when called with high ATR (> 5.0), then it returns `action: "BUY"` but with `confidence` reduced by 10% (i.e. `0.765` not `0.85`)
- Given `None` as any input parameter, when called, then it returns `action: "HOLD"`, `confidence: 0.0`, and a reason indicating the invalid input — and does not raise
- Given a non-numeric string or negative value for `adx`, `atr`, or `volume_ratio`, when called, then it returns `confidence: 0.0` and does not raise
- Given `adx=26, momentum=0.05, volume_ratio=1.5` (BUY conditions met exactly at boundary), when called, then it returns `action: "BUY"` (strict `>` for ADX, `>=` for volume_ratio)
- Given `adx=25, momentum=0.05, volume_ratio=1.5` (ADX exactly at 25 — not > 25), when called, then it falls to WATCHLIST rule (ADX >= 20 AND <= 25), returning `action: "WATCHLIST"`

### Definition of Done
- [ ] `data/signals.py` implemented following module-per-concern pattern
- [ ] Exception boundary: outer `try/except` — never raises to caller
- [ ] `_CONFIDENCE_MAP` and `_INVALID_INPUT_FALLBACK` as module-level constants
- [ ] `_safe_indicator` private helper validates all four inputs
- [ ] `tests/test_signals.py` written with all tests Strong (no Meaningless, no Weak)
- [ ] All 448 existing tests still pass after adding the new module
- [ ] Test review passes: Recommendation: Ready

---
