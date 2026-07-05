# Analysis: User Profile Influence (Profile Advisor)
Date: 2026-07-03
Story: 2026-07-03-user-profile-influence-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 data pipeline with 17 existing modules in `data/`. No web framework, ORM, or persistence. Two existing modules already carry a risk-tolerance concept: `portfolio.py` accepts `risk_tolerance` as a float parameter, and `risk.py` returns a classified `risk_level` string. Neither is reused by this module — it is entirely self-contained with pure Python stdlib only.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `risk_tolerance` parameter | `data/portfolio.py:77` | Float in [0,1] already used by SLSQP optimizer; establishes the clamped-float convention for risk inputs |
| `risk_level` classifier | `data/risk.py:74` | Threshold-table lookup returning "Low"/"Medium"/"High"/"Critical" — same ordered-lookup pattern applies to volatility modifier selection |
| `generate_recommendation` action output | `data/screener.py:24` | Returns title-case `"Buy"/"Sell"/"Hold"` — upstream signal producer; caller must normalise case before passing to this module |
| `aggregate_signals` action convention | `data/meta_agent.py:10` | Uses all-caps `"BUY"/"SELL"/"HOLD"` — second upstream signal format; normalisation in this module must handle both |
| `run_backtest` case normalisation | `data/backtester.py` | Already normalises action strings to uppercase via `str(action).upper()` — identical pattern applies here |
| `_EMPTY_RESULT` constant pattern | `data/risk.py:5`, `data/meta_agent.py:1`, `data/notifier.py`, `data/backtester.py` | Module-level fallback constant, always returned via `.copy()`; this module uses an empty dict `{}` as fallback (variable output shape, no fixed keys) |
| Skip-invalid-per-item semantics | `data/knowledge_graph.py`, `data/graph_reasoning.py` | Valid items processed even when some are malformed; same pattern for profile validation |

### Missing / Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/profile_advisor.py` | New module | Entire module is new |
| `get_profile_recommendations(ticker, signal, volatility, profiles=None)` | Public function | Main entry point; must match universal pipeline rules |
| `_EMPTY_PROFILES_RESULT` | Module-level constant | Value is `{}` (empty dict) — not a fixed-key dict — because output keys are determined by the profiles input |
| `_DEFAULT_PROFILES` | Module-level constant | List of three dicts: `{name, risk_tol}` for Conservative (0.2), Balanced (0.5), Aggressive (0.9) |
| `_VOLATILITY_MODIFIERS` | Module-level constant | Dict mapping `"HIGH" → 0.5`, `"MEDIUM" → 0.75`, `"LOW" → 1.0`; used for O(1) modifier lookup |
| `_VALID_SIGNALS` | Module-level constant | Frozenset `{"BUY", "SELL", "HOLD"}`; validated after case normalisation |
| `_BUY_THRESHOLD` | Module-level constant | `0.3` — the position_size cutoff above which action is "BUY"; avoids magic literal |
| `_validate_profile(profile)` | Private helper | Returns `(name, risk_tol)` tuple or None; rejects missing keys, non-string name, non-numeric or out-of-range risk_tol |
| `_build_reasoning(ticker, signal, volatility, risk_tol, position_size, modifier)` | Private helper | Produces the human-readable reasoning string for one profile |
| `tests/test_profile_advisor.py` | Test file | No mocking needed — pure Python function with no external calls |

---

## Strategic Approach

Build `data/profile_advisor.py` as a pure rule-engine module with no external dependencies, following the same structure as `data/screener.py`: a thin public function that validates inputs, delegates to a per-profile computation, and returns a dict of results. The core logic is a single arithmetic formula — `base_size × volatility_modifier × risk_tol` — applied independently per profile, making each profile's output independently testable and verifiable. All module-level constants (`_VOLATILITY_MODIFIERS`, `_VALID_SIGNALS`, `_BUY_THRESHOLD`, `_DEFAULT_PROFILES`) are defined once and referenced everywhere, eliminating magic literals. The per-item skip-invalid pattern (established in `knowledge_graph.py` and `graph_reasoning.py`) handles malformed profiles gracefully without aborting the entire call.

---

## Key Design Decisions

- **`_EMPTY_PROFILES_RESULT = {}`:** This module's fallback constant is an empty dict, not a dict with fixed None-valued keys. The output shape depends on which profiles are supplied; there is no meaningful "empty shape" to define. `.copy()` on `{}` is still correct and consistent with the `.copy()` convention used across all other modules.
- **Case normalisation on all string inputs:** Both `signal` and `volatility` are uppercased immediately on entry (`str(value).upper()`), so `"buy"`, `"Buy"`, and `"BUY"` are all accepted. This matches the pattern established in `backtester.py` and handles both `screener.py` (title-case) and `meta_agent.py` (all-caps) signal formats.
- **`SELL` maps to `base_size = 0.0`:** The story explicitly specifies long-only — no short positions. A SELL signal means "exit" (position_size=0.0), not "go short". This produces HOLD for all profiles on SELL input, which is the correct long-only behaviour.
- **`_validate_profile` returns a tuple or None:** Consistent with `_parse_agent_entry` in `meta_agent.py` — invalid entries return None to signal skip, not a raised exception.
- **`_DEFAULT_PROFILES` is a module-level list constant:** When `profiles=None`, the function uses this constant directly. It is never mutated inside the function (read-only iteration only), so no defensive copy is needed on the list itself.
- **No numpy:** The formula is a single float multiplication — numpy would add import weight for zero benefit. Pure Python `float()` wrapping ensures native-type output.
- **`_BUY_THRESHOLD = 0.3` as a named constant:** The threshold is a deliberate design parameter, not a magic number. Naming it allows future stories to adjust it without hunting for inline literals.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Caller passes `signal="Buy"` (title-case from `generate_recommendation`) | Medium | Handled by `str(signal).upper()` normalisation on entry; test both formats explicitly |
| All profiles in a custom list are invalid | Low | Must return `_EMPTY_PROFILES_RESULT.copy()` — guard after the per-profile loop |
| `risk_tol` of exactly `0.0` or `1.0` on boundary | Low | Both are valid; `0.0` → position_size always 0.0 → HOLD; `1.0` → full signal with only volatility modifier applied |
| Duplicate profile names in custom list | Low | Last-writer-wins (dict key assignment); not an error — caller's responsibility |
| `ticker` is None or non-string | Low | Only used in reasoning string; `str(ticker)` coercion is sufficient; do not validate |
| `_EMPTY_PROFILES_RESULT` shallow copy on empty dict | Low | `{}.copy()` always produces a fresh empty dict with no shared references — no risk |
| `position_size` at exactly 0.3 | Low | `> 0.3` threshold means 0.3 exactly → HOLD; test the boundary explicitly |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns dict with 3 keys, each with `action`, `position_size`, `reasoning` | Needs work | New module; schema defined by `_DEFAULT_PROFILES` constant |
| Conservative ≤ balanced ≤ aggressive position_size on BUY; conservative → HOLD on HIGH | Needs work | `1.0 × 0.5 × 0.2 = 0.10` ≤ threshold; formula enforces monotone ordering by risk_tol |
| Aggressive BUY + LOW → position_size = 0.9 | Needs work | `1.0 × 1.0 × 0.9 = 0.90`; exact float verifiable |
| SELL or HOLD signal → position_size = 0.0, action = "HOLD" for all profiles | Needs work | `base_size = 0.0` for both; formula collapses to 0.0 regardless of modifier or risk_tol |
| Custom profiles list replaces defaults | Needs work | `if profiles is None: profiles = _DEFAULT_PROFILES` |
| Invalid signal → `_EMPTY_PROFILES_RESULT.copy()` | Needs work | Pre-flight check after case normalisation |
| Invalid volatility → `_EMPTY_PROFILES_RESULT.copy()` | Needs work | Pre-flight check after case normalisation |
| Invalid/malformed profile dicts silently skipped; all-invalid → empty | Needs work | `_validate_profile` returns None; post-loop guard for empty results dict |
| Exception → `_EMPTY_PROFILES_RESULT.copy()`, never raises | Needs work | Outer `try/except Exception` wraps entire function body |

---

## Dependencies

- No existing `data/` modules are imported — this module is fully self-contained
- `generate_recommendation` in `data/screener.py` is the primary upstream signal producer; its title-case output must be normalised by callers before passing here (or this module handles it, which it does)
- `run_backtest` in `data/backtester.py` and `aggregate_signals` in `data/meta_agent.py` are downstream consumers of signals in the same pipeline — neither is modified by this story
- No changes to `requirements.txt` — pure Python stdlib only
