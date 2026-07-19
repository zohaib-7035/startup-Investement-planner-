# User Story: VC Brain — Trust Score & Evidence-Backed Investment Memo
Date: 2026-07-19
Source: Pasted text — VC Brain hackathon brief (Evidence-Backed Investment Memos & Trust Score)

---

## Story 5: Claim Extraction & Trust Score Verification

**As a** VC analyst using VC Brain,
**I want** `extract_claims()` to extract structured claims with confidence scores from pitch deck text using the `knowledge_graph.py` triple-extraction pattern, and `verify_claim()` to cross-check each claim against available profile evidence — marking each as "verified", "unverifiable", or "contradicted",
**So that** every claim reaching the investment memo has a traceable evidence chain and a machine-readable trust signal, satisfying the brief's requirement that "every claim must trace to evidence with a confidence level."

### Scope In
- `Claim` dataclass: `claim_text (str)`, `category (Literal["traction", "revenue", "team", "market_size", "other"])`, `confidence_score (float 0-1)`, `source_reference (str)` — which raw_source it came from
- `VerifiedClaim` dataclass: `claim (Claim)`, `status (Literal["verified", "unverifiable", "contradicted"])`, `verification_confidence (float 0-1)`, `supporting_evidence (list[str])`, `contradiction_note (str | None)`
- `extract_claims(profile: FounderProfile) -> list[Claim]`: applies `knowledge_graph.py`'s Subject→Relation→Object triple extraction (with confidence scores) to `profile.raw_sources` text content; maps each extracted triple to a `Claim` with `category` inferred from the predicate/object keywords (e.g. "users" / "revenue" / "engineers" / "market")
- `verify_claim(claim: Claim, available_evidence: list) -> VerifiedClaim`: cross-checks the claim against profile signals and other claims; marks as:
  - `"verified"` — at least one evidence item corroborates it at verification_confidence > 0.6
  - `"unverifiable"` — no evidence exists to confirm or deny (NOT the same as false); the claim is preserved explicitly, never silently dropped
  - `"contradicted"` — available evidence directly conflicts with the claim; `contradiction_note` is non-empty
- Gap flagging: when a standard investable section (cap table, financials) has no data at all in `profile.raw_sources`, `extract_claims()` MUST emit a synthetic `Claim` with `claim_text="not disclosed"` for that section — surfaces in the memo rather than being omitted silently

### Scope Out
- Real-time external verification APIs (Crunchbase, LinkedIn, Companies House) — profile signals only
- Claim deduplication logic — preserve all claims including overlapping ones
- Re-extraction from PDF binary — plain text `raw_sources` strings only
- Storing `VerifiedClaim` objects to disk between sessions
- Batch convenience wrapper (just call `verify_claim()` per item in the caller)

### Acceptance Criteria
- Given a `FounderProfile` with pitch deck text containing "We have 500K active users", when `extract_claims()` is called, then the returned list contains a `Claim` with `category="traction"`, `claim_text` referencing "500K", and `confidence_score > 0.5`
- Given a `Claim` asserting "500K users" and profile signals showing `star_growth` score of 10 (very low traction), when `verify_claim()` is called, then `status == "contradicted"` and `contradiction_note` is a non-empty string
- Given a claim about cap table structure with no supporting data anywhere in the profile, when `verify_claim()` is called, then `status == "unverifiable"` and the `VerifiedClaim` is returned (not dropped or None)
- Given a `FounderProfile` whose `raw_sources` contains no revenue information, when `extract_claims()` is called, then the returned list contains a `Claim` with `claim_text` containing "not disclosed" for the revenue category
- Given a `FounderProfile` with GitHub signals showing `contributor_count=3` and pitch deck text claiming "a team of 3 engineers", when `verify_claim()` is called for that team claim, then `status == "verified"` and `supporting_evidence` references the contributor signal
- Given Ollama is unavailable (mocked network failure), when `extract_claims()` is called, then it does not raise and returns a list containing at least the "not disclosed" gap-flag claims

### Definition of Done
- [ ] `Claim` and `VerifiedClaim` dataclasses defined in `data/trust_score.py`
- [ ] `extract_claims()` implemented — reuses `knowledge_graph.py` Ollama call pattern; offline fallback returns gap-flag claims only
- [ ] `verify_claim()` implemented — verified / unverifiable / contradicted logic, confidence levels
- [ ] "Contradicted" test passes with deliberately contradictory profile (deck claims 500K users; GitHub star signal score ≤ 10)
- [ ] "Unverifiable" test passes — claim preserved in output, status == "unverifiable"
- [ ] "Verified" test passes — corroborating signal sets status to "verified"
- [ ] Gap-flagging test: section with no data produces "not disclosed" claim in extract_claims() output
- [ ] Offline fallback test: mocked Ollama failure does not raise; returns gap-flag claims
- [ ] All tests pass with Ollama mocked via `@patch("data.trust_score.requests.post", ...)`

---

## Story 6: Evidence-Backed Investment Memo with Mandatory Gap Flagging

**As a** VC analyst using VC Brain,
**I want** `generate_memo()` to produce a structured `InvestmentMemo` where every required section is present and every claim is traceable back to a `VerifiedClaim` — and optional sections are either populated when data exists or explicitly flagged "not disclosed" when it does not — and `export_memo_markdown()` / `export_memo_pdf()` to produce investor-ready output,
**So that** the investment memo is trustworthy by construction: every claim is traceable, every gap is named, and no fabricated data can reach an investor — satisfying the brief's scoring criterion that "a memo that marks its own gaps is considered MORE trustworthy, not less."

### Scope In
- `MemoSection` dataclass: `title (str)`, `content (str)`, `claims (list[VerifiedClaim])`, `is_available (bool)`, `unavailability_reason (str | None)`
- `InvestmentMemo` dataclass: `company (str)`, `date (str)`, `required_sections (list[MemoSection])` — exactly five, in order: Company snapshot, Investment hypotheses, SWOT, Problem & product, Traction & KPIs — `optional_sections (list[MemoSection])`, `overall_trust_score (float 0-1)` computed as the mean `verification_confidence` of all `VerifiedClaim` objects
- `generate_memo(profile: FounderProfile, screening: ScreeningResult, verified_claims: list[VerifiedClaim]) -> InvestmentMemo`:
  - **Company snapshot**: one paragraph assembled from `profile.name`, `profile.company`, `profile.sector`, `profile.stage`; cites any "verified" team or company claims
  - **Investment hypotheses**: bulleted list derived from each axis's `evidence` strings in `screening`; each bullet cites a specific `VerifiedClaim` from `verified_claims` (or marks the evidence as unverified if no matching claim exists)
  - **SWOT**: strengths from high axis scores + verified claims; weaknesses from risk flags + contradicted claims; opportunities from market axis + uncontradicted traction claims; threats from risk flags + unverifiable claims
  - **Problem & product**: assembled from `verified_claims` with `category in ("market_size", "other")`; if none, content states "insufficient data to characterise problem space"
  - **Traction & KPIs**: assembled from `verified_claims` with `category in ("traction", "revenue")`; if none, `is_available=False` and `unavailability_reason="not disclosed"`
  - **Optional sections** (Financials & round structure, Cap table, Competition, Market sizing, Due diligence log, Exit perspective): `is_available=True` only when supporting `VerifiedClaim` objects exist; otherwise `is_available=False`, `unavailability_reason="not disclosed"` — never fabricated
  - Every `MemoSection.content` in required sections must have at least one `VerifiedClaim` in `MemoSection.claims`; an empty `claims` list is a generation error
- `export_memo_markdown(memo: InvestmentMemo) -> str`:
  - Header block: company name, date, `overall_trust_score` as percentage
  - Required sections rendered in order; unavailable Traction section rendered as `> **[Traction & KPIs: not disclosed]**`
  - Optional sections: present ones rendered normally; absent ones rendered as `> **[Section title: not disclosed]**`
  - Traceability table appended: `| Claim | Category | Status | Confidence |` for every `VerifiedClaim` referenced in the memo
- `export_memo_pdf(memo: InvestmentMemo) -> bytes`: converts the `export_memo_markdown()` output to PDF; `markdown` + `weasyprint` preferred; fall back to `reportlab` text layout if weasyprint unavailable; returns non-empty bytes; must not raise on missing optional data

### Scope Out
- Flask `/memo` route integration — function-layer only
- LLM-generated free-text prose for any section — `generate_memo()` assembles structured data only; no Ollama call in this function
- Multi-founder comparison or side-by-side memos
- Email delivery or file-system persistence of exported memos
- Revision / versioning of memos
- HTML export (markdown and PDF only)

### Acceptance Criteria
- Given a `FounderProfile` with `sector="AI/ML"`, `stage="pre-seed"`, a `ScreeningResult`, and a list of `VerifiedClaim` objects, when `generate_memo()` is called, then `InvestmentMemo.required_sections` contains exactly 5 sections with non-empty content and non-empty `claims` lists
- Given a profile with no revenue `VerifiedClaim` objects, when `generate_memo()` is called, then the optional Financials section has `is_available=False` and `unavailability_reason` contains "not disclosed"
- Given the generated `InvestmentMemo`, when `export_memo_markdown()` is called, then the output contains the literal string "not disclosed" for every section with `is_available=False` and contains no revenue figures that were not present in a `VerifiedClaim`
- Given any `InvestmentMemo`, when each required section is inspected, then `MemoSection.claims` is non-empty — no section contains unsourced prose
- Given a valid `InvestmentMemo`, when `export_memo_pdf()` is called, then it returns a `bytes` object with length > 0 without raising any exception
- Given a synthetic founder from `sample_founders.json` processed end-to-end through `extract_claims()` → `verify_claim()` → `generate_memo()` → `export_memo_markdown()`, then the output contains all 5 required section headings, a trust score header, and at least one "not disclosed" label on a missing optional section

### Definition of Done
- [ ] `MemoSection` and `InvestmentMemo` dataclasses defined in `data/memo_generator.py`
- [ ] `generate_memo()` implemented — 5 required sections always present with claims; optional sections flagged when missing
- [ ] "No fabricated data" test: assert no financial figures appear in memo when no revenue `VerifiedClaim` was provided (check `export_memo_markdown()` output with regex)
- [ ] "All required sections present" test: 5 sections, all with non-empty `claims`, for a sample_founders.json founder
- [ ] "Optional section flagged" test: Financials `is_available=False` when no revenue claims exist
- [ ] "Empty claims guard" test: any required section with `claims=[]` is a generation error — assert it cannot happen
- [ ] `export_memo_markdown()` implemented — trust score header, traceability table, "not disclosed" callouts
- [ ] `export_memo_pdf()` implemented — non-empty bytes, no exception on missing optional data
- [ ] Sample memo for one `sample_founders.json` founder reviewed manually for investor readability
- [ ] Full pytest suite passing with Ollama mocked via `@patch("data.trust_score.requests.post", ...)`

---

## Data Flow Diagram

```
FounderProfile (raw_sources)
    │
    ▼
extract_claims()  ← knowledge_graph.py Ollama pattern (mocked in CI)
    │
    ▼  list[Claim]
verify_claim() × N  ← cross-checks profile.key_signals + other claims
    │
    ▼  list[VerifiedClaim]
generate_memo(profile, ScreeningResult, verified_claims)
    │
    ▼  InvestmentMemo
    ├── export_memo_markdown()  →  str
    └── export_memo_pdf()       →  bytes
```

---

## LLM-Dependent vs. Rule-Based Summary

| Function | Mode | Notes |
|----------|------|-------|
| `extract_claims()` | **LLM-dependent** | Reuses `knowledge_graph.py` Ollama call. Offline fallback returns gap-flag "not disclosed" claims only; never raises. |
| `verify_claim()` | **Rule-based — offline** | Signal cross-check logic only. No Ollama needed. |
| `generate_memo()` | **Rule-based — offline** | Assembles `VerifiedClaim` + `ScreeningResult` data. No LLM prose generation. |
| `export_memo_markdown()` | **Rule-based — offline** | String rendering only. |
| `export_memo_pdf()` | **Rule-based — offline** | PDF conversion. Must not raise on missing optional data. |

**CI-safe tests** (no Ollama required): all `verify_claim()` tests, all `generate_memo()` tests, all export tests — using pre-built `VerifiedClaim` fixtures.

**Ollama-dependent tests** (require `ollama serve` + `ollama pull llama3.2:3b`): `extract_claims()` happy-path only. Mock via `@patch("data.trust_score.requests.post", ...)` for CI.

**Key safeguard carried forward from brief:**
> "A memo that marks its own gaps is considered MORE trustworthy, not less."
>
> No `generate_memo()` implementation may fabricate or infer data for a section where no `VerifiedClaim` exists. Silent omission and fabrication are equally forbidden. The only valid response to missing data is an explicit "not disclosed" flag.
