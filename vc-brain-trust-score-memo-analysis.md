# Analysis: VC Brain — Trust Score & Evidence-Backed Investment Memo
Date: 2026-07-19
Story: vc-brain-trust-score-memo-story.md
Scope: BE-only
Repos scanned: D:\claude\project\vc-brain (local Python project)

---

## Project Fingerprint

Python 3.9 Flask app with a flat `data/` module layer. All business logic lives in stateless functions or minimal classes — no ORM, no database, no frontend. LLM calls use local Ollama (`llama3.2:3b`) via `requests.post` to `/api/chat`; every module with an Ollama dependency has a broad `except Exception` offline fallback. Key existing modules in scope: `knowledge_graph.py` (triple extraction pattern to reuse), `scoring_engine.py` (produces `ScreeningResult` with three `AxisScore` objects + `risk_flags`), `memo_generator.py` (v1 — flat-field `InvestmentMemo`, incompatible with story requirements), `founder_data.py` (`FounderProfile`, `ingest_pitch_deck`), `sourcing.py` (`load_sample_founders` from `sample_founders.json`). No PDF library present in `requirements.txt` — `reportlab` must be added.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `extract_relationships()` | `data/knowledge_graph.py:103` | Triple extraction via Ollama — system prompt, `_call_ollama()`, `_parse_llm_response()`. The exact pattern `extract_claims()` must adapt. |
| `_call_ollama()` | `data/knowledge_graph.py:31` | `requests.post` to `/api/chat`, `stream=False`, `timeout=120`, returns content string or `None`. Replicate, don't import — different system prompt. |
| `_parse_llm_response()` | `data/knowledge_graph.py:51` | Strips fences, extracts JSON array, validates keys, clamps confidence. Reuse logic for claim parsing. |
| `FounderProfile` | `data/founder_data.py:34` | `name, company, sector, stage, github_url, key_signals (dict), raw_sources (list[str])`. Input to `extract_claims()`. |
| `ingest_pitch_deck()` | `data/founder_data.py:142` | Stores `"pitch_deck_text"` marker in `raw_sources` — does NOT preserve original text. **Critical gap for `extract_claims()`.** |
| `ScreeningResult` | `data/scoring_engine.py:93` | `profile, founder_axis, market_axis, idea_vs_market_axis (AxisScore), risk_flags (list[RiskFlag]), thesis_match (bool), thesis_reason (str)`. Input to `generate_memo()`. |
| `AxisScore` | `data/decision_engine.py:13` | `name, score (float 0-100), trend, rationale, evidence (list[str])`. Evidence strings feed Investment Hypotheses and SWOT sections. |
| `RiskFlag` | `data/risk_flags.py:11` | `category, description, severity`. Feeds SWOT weaknesses/threats. |
| `InvestmentMemo` (v1) | `data/memo_generator.py:18` | Flat dataclass: `company_snapshot`, `investment_hypotheses`, `swot`, `problem_and_product`, `traction_and_kpis`, `financials`, `cap_table`, `team_bios` — all strings. **Incompatible with story's `MemoSection`-based structure.** |
| `generate_memo()` (v1) | `data/memo_generator.py:60` | Signature: `(profile, thesis_result, risk_flags, decision)`. **Must be replaced** — story requires `(profile, ScreeningResult, verified_claims)`. |
| `NOT_DISCLOSED` | `data/memo_generator.py:14` | String constant `"[Not Disclosed]"`. Keep and reuse in v2. |
| `load_sample_founders()` | `data/sourcing.py:246` | Loads `data/sample_founders.json` as `list[FounderProfile]`. Use for end-to-end sample memo test. |
| `sample_founders.json` | `data/sample_founders.json` | Synthetic profiles: Priya/FinAI Labs, Marcus/MediTrack Pro, Sofia/DeployKit. `key_signals` has `total_stars` (not `star_growth`), `contributor_count`, `commit_frequency`, `recency`, `claimed_users`. |
| `test_memo_generator.py` | `tests/test_memo_generator.py` | 10 existing tests against v1 interface — all will fail after v2 refactor. Must be replaced entirely. |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/trust_score.py` | New module | Does not exist. Contains `Claim`, `VerifiedClaim`, `extract_claims()`, `verify_claim()`. |
| `Claim` | New dataclass | `claim_text, category, confidence_score, source_reference`. |
| `VerifiedClaim` | New dataclass | `claim (Claim), status, verification_confidence, supporting_evidence (list[str]), contradiction_note (str\|None)`. |
| `extract_claims()` | New function | Adapts `knowledge_graph.py` pattern with a VC-oriented Ollama prompt; also emits deterministic gap-flag synthetic claims for missing standard sections. |
| `verify_claim()` | New function | Rule-based offline; cross-checks against `profile.key_signals` signals and other claims in `available_evidence`. |
| `_GAP_SECTIONS` | New constant | List of sections that require explicit "not disclosed" flagging if absent (cap_table, financials, revenue). |
| `MemoSection` | New dataclass | `title, content, claims (list[VerifiedClaim]), is_available (bool), unavailability_reason (str\|None)`. |
| `InvestmentMemo` (v2) | Replace existing | `company, date, required_sections (list[MemoSection]), optional_sections (list[MemoSection]), overall_trust_score (float)`. Breaking change. |
| `generate_memo()` (v2) | Replace existing | New signature: `(profile, ScreeningResult, verified_claims) -> InvestmentMemo`. No Ollama call. |
| `export_memo_markdown()` | New function | `(memo) -> str`. Trust score header + 5 required sections + optional "not disclosed" callouts + traceability table. |
| `export_memo_pdf()` | New function | `(memo) -> bytes`. Converts markdown output to PDF via `reportlab`; no exception on missing data. |
| `reportlab` | New dependency | Add to `requirements.txt`. Not currently present. |
| `tests/test_trust_score.py` | New test file | Covers all `Claim`, `VerifiedClaim`, `extract_claims()`, `verify_claim()` ACs. |
| `tests/test_memo_generator.py` | Full replacement | All 10 v1 tests must be replaced with v2 tests (MemoSection structure, ScreeningResult input, traceability assertions). |

---

## Strategic Approach

`data/trust_score.py` is a new module that follows the same stateless-function pattern as all other `data/*.py` modules. `extract_claims()` adapts `knowledge_graph.py`'s `_call_ollama()` call with a new VC-oriented system prompt requesting claims with categories (`traction`, `revenue`, `team`, `market_size`, `other`) and confidence scores; `_parse_llm_response()` logic is reused for fence-stripping and JSON extraction. `verify_claim()` is purely rule-based — no Ollama call — cross-checking the claim's category against `profile.key_signals` and the `available_evidence` list (caller passes signal dicts from `generate_founder_signals()` plus other extracted claims). `data/memo_generator.py` is a targeted rewrite: `InvestmentMemo` and `generate_memo()` are replaced with the `MemoSection`-based v2 structure; `NOT_DISCLOSED` is kept; `export_memo_markdown()` and `export_memo_pdf()` are appended. The existing 10 `test_memo_generator.py` tests must be replaced in full — they test the v1 interface which is incompatible.

---

## Key Design Decisions

- **Adapt, don't import `knowledge_graph.py`:** `extract_claims()` needs a different system prompt (VC claims, not financial entity relationships) and different output keys (`claim_text`, `category`, `confidence_score`). Duplicate the `_call_ollama()` pattern in `trust_score.py` rather than importing from `knowledge_graph.py` — same Ollama URL/model constants, different prompt.

- **`available_evidence` type is `list[dict]`:** Each element is either a signal entry `{"signal": str, "score": float, "direction": str}` (from `generate_founder_signals()`) or another claim reference `{"claim_text": str, "category": str, "confidence_score": float}`. This keeps `verify_claim()` signature simple while allowing the caller to pass whatever evidence is available.

- **Pitch deck text access:** `ingest_pitch_deck()` stores `"pitch_deck_text"` as a marker, not the actual text. `extract_claims()` must treat items in `raw_sources` longer than 100 characters that don't start with `http` as actual text content to extract from. For the hackathon demo, the caller passes raw pitch deck text directly as an element of `profile.raw_sources` before calling `extract_claims()`.

- **`sample_founders.json` uses `total_stars` not `star_growth`:** `generate_founder_signals()` reads `star_growth` from `key_signals`; sample founders have `total_stars`. In `verify_claim()`, treat `total_stars` as a fallback for `star_growth` to avoid all sample-founder traction claims being `"unverifiable"` due to missing signal key.

- **`generate_memo()` is assembly-only — no LLM call:** All five required sections are assembled from structured inputs (`ScreeningResult` evidence strings, `VerifiedClaim` data, `RiskFlag` categories). No Ollama call in this function — that constraint is load-bearing for the "no fabricated data" guarantee.

- **`overall_trust_score` default:** When `verified_claims` is empty (offline fallback), `overall_trust_score` defaults to `0.0` rather than raising a `ZeroDivisionError` from taking the mean of an empty list.

- **PDF via `reportlab`:** Add `reportlab` to `requirements.txt`. `export_memo_pdf()` renders sections as paragraph blocks using `reportlab.platypus`. This avoids weasyprint's system-level CSS/HTML dependencies that are fragile in CI.

- **Breaking change isolation:** All 10 existing `test_memo_generator.py` tests reference the v1 `generate_memo(profile, thesis_result, risk_flags, decision)` signature and flat-field attributes. These must be replaced in the same operation as the `memo_generator.py` rewrite — not deferred.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| `test_memo_generator.py` — 10 tests test v1 interface | High | Will all fail after v2 refactor. Must be replaced in Operation 1 of the canvas, before any v2 code is written. Treat as a planned migration, not a regression. |
| `raw_sources` does not contain pitch deck text | High | `ingest_pitch_deck()` stores `"pitch_deck_text"` marker only. `extract_claims()` will find no text to extract from for sample founders unless raw text is injected. Canvas must define how text reaches `raw_sources` (or accept text as a secondary input to `extract_claims()`). |
| `sample_founders.json` uses `total_stars` vs `generate_founder_signals()`'s `star_growth` key | Medium | Traction claim verification for sample founders will always be `"unverifiable"` if only `star_growth` is checked. `verify_claim()` must fall back to `total_stars` as well. |
| `overall_trust_score` ZeroDivisionError on empty claims | Medium | If `verified_claims=[]` (offline Ollama fallback), mean confidence fails. Default to `0.0`. |
| `export_memo_pdf()` — `reportlab` not in requirements.txt | Medium | Must add to `requirements.txt` before Op that implements it; otherwise import fails in tests. |
| LLM claim extraction quality (no Ollama in CI) | Medium | `extract_claims()` happy-path depends entirely on LLM output. Gap-flag synthetic claims are the only CI-verifiable output. Document this explicitly in test file. |
| "No fabricated data" test — regex scope | Low | Test must check the markdown output of `export_memo_markdown()` for absence of revenue figures (`\$\d`, `€\d`, `£\d`, `\d+[KMB] ARR`) when no revenue `VerifiedClaim` was provided. Define the pattern clearly in the canvas. |
| `MemoSection.claims` empty guard | Low | Any required section with `claims=[]` is defined as a generation error. `generate_memo()` must provide at least one synthetic "unverified" claim (from `NOT_DISCLOSED` logic) for sections with no traction data, rather than leaving `claims=[]`. |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| `extract_claims()` pulls structured claims with confidence scores from pitch deck text | Needs work | `raw_sources` text access is the blocker — must define how text reaches the profile. Once solved, adapting `knowledge_graph.py` prompt is straightforward. |
| `verify_claim()` distinguishes verified / unverifiable / contradicted with at least one deliberate contradiction test | Needs work | Rule logic is new. Test fixture: claim "500K users" + `star_growth` signal score ≤ 10 → `"contradicted"`. GitHub `contributor_count=3` + deck "3 engineers" → `"verified"`. Cap table claim + no signals → `"unverifiable"`. All achievable rule-based. |
| `generate_memo()` produces all 5 required sections; flags at least one optional section "not disclosed" | Partially supported | v1 already produces 5 sections and flags optionals. v2 refactors to `MemoSection` structure — behaviour is the same but the interface changes completely. `ScreeningResult` replaces `DecisionResult` as input. |
| No fabricated data in generated memo (explicit test) | Needs work | New test: pass a `ScreeningResult` and `verified_claims` with no revenue data; call `export_memo_markdown()`; assert no revenue-pattern regex matches in output. |
| `export_memo_markdown()` and `export_memo_pdf()` produce valid readable output | Needs work | Both functions are new. `export_memo_pdf()` requires adding `reportlab` to `requirements.txt`. |
| End-to-end sample memo for a `sample_founders.json` founder | Needs work | Achievable once all components exist. Recommend Sofia/DeployKit (SaaS, seed, `total_stars=210`, `commit_frequency=11`) as the demo founder — richest signals. |

---

## Dependencies

- `data/knowledge_graph.py` — `_call_ollama()` and `_parse_llm_response()` patterns copied into `trust_score.py`; the original module is not modified
- `data/founder_data.py` — `FounderProfile` is the primary input type for both new modules; `ingest_pitch_deck()` text-storage behaviour is a known gap
- `data/founder_signals.py` — `generate_founder_signals()` output (signal dicts) is the primary `available_evidence` passed to `verify_claim()`
- `data/scoring_engine.py` — `ScreeningResult` and `AxisScore` are inputs to `generate_memo()` v2
- `data/risk_flags.py` — `RiskFlag` feeds SWOT section in `generate_memo()` v2
- `data/sourcing.py` — `load_sample_founders()` used in end-to-end memo test
- `data/decision_engine.py` — `AxisScore.evidence` strings consumed by `generate_memo()` v2; `DecisionResult` is NO LONGER an input to `generate_memo()` after v2 refactor
- `tests/test_memo_generator.py` — **all 10 existing tests must be replaced**; treat as a planned migration
- `requirements.txt` — `reportlab` must be added before implementing `export_memo_pdf()`
