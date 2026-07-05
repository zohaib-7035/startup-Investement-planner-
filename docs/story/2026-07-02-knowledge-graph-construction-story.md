# User Story: Knowledge Graph Construction
Date: 2026-07-02
Source: Pasted text

---

## Story 12: Extract Financial Relationships from Text as Knowledge Graph Triples

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that reads any plain-text sentence or passage about financial relationships and returns a list of typed, confidence-scored triples in the form `{source, relation, target, confidence}`,
**So that** the platform can construct a queryable knowledge graph of company-level financial dependencies (supply chains, partnerships, subsidiaries, competitors) from unstructured text without requiring a separate NLP service.

### Scope In
- Accept a single `text` string (a sentence or short passage) as input
- Call the Anthropic Claude API (Haiku model) with a system prompt that instructs the model to act as a financial knowledge graph extraction agent
- The system prompt must instruct the model to extract all financially meaningful relationships present in the text and return them as a JSON array of triple objects
- Each triple must contain exactly four keys: `source` (string — the entity the relationship originates from), `relation` (string — the relationship type in upper-case, e.g. SUPPLIER, COMPETITOR, SUBSIDIARY, PARTNER, CUSTOMER), `target` (string — the entity the relationship points to), and `confidence` (float 0.0–1.0 — how certain the model is that this relationship is stated or strongly implied by the provided text)
- Parse the model's JSON array response; strip markdown fences before parsing (reuse the fence-stripping pattern from `data/sentiment.py` and `data/rag_answer.py`)
- Clamp each `confidence` value to [0.0, 1.0] using `max(0.0, min(1.0, raw))` — same pattern as `data/rag_answer.py`
- Validate each triple dict in `_parse_llm_response`: all four keys must be present, `source`/`relation`/`target` must be non-empty strings, `confidence` must be castable to float — skip invalid triples rather than returning an error (partial extraction is better than total failure)
- Return `[]` when: the input text is empty or whitespace-only, the API call raises any exception, the response is not valid JSON, or no valid triples can be extracted
- Live in `data/knowledge_graph.py` as `extract_relationships(text: str) -> list[dict]`
- Covered by `tests/test_knowledge_graph.py` with the Anthropic client mocked (no live API calls in tests)

### Scope Out
- No graph database storage — this function returns Python dicts only; persistence is a separate story
- No entity disambiguation or normalisation (e.g. "NVIDIA Corp" vs "NVIDIA" are treated as-is from the model output)
- No cross-sentence or document-level coreference resolution — single text input only
- No predefined relation vocabulary enforcement — the model chooses the relation type; validation only checks that a non-empty string is present
- No batch processing of multiple texts in a single call
- No deduplication of extracted triples (if the model returns the same triple twice, both are included)
- No streaming or partial result delivery

### Acceptance Criteria
- Given a sentence describing a supply-chain dependency (e.g. "NVIDIA relies heavily on TSMC for manufacturing advanced AI chips."), when `extract_relationships(text)` is called, then it returns a non-empty list containing at least one triple where `source` is "NVIDIA", `relation` contains "SUPPLIER" or "MANUFACTUR" (case-insensitive match acceptable), and `target` is "TSMC"
- Given a successful API call, when each dict in the returned list is inspected, then it contains exactly four keys: `source`, `relation`, `target`, `confidence`
- Given a successful API call, when `confidence` is inspected on each triple, then it is a Python float between 0.0 and 1.0 inclusive
- Given an empty string `""` is passed as `text`, when `extract_relationships` is called, then it returns `[]` without calling the Anthropic API and without raising
- Given the Anthropic API raises any exception, when `extract_relationships` is called, then it returns `[]` without raising
- Given the API returns a response with markdown fences around the JSON array, when the response is parsed, then the fences are stripped and the triples are parsed correctly
- Given the API returns a JSON array where one triple is missing the `confidence` key, when `extract_relationships` is called, then the invalid triple is skipped and the remaining valid triples are returned
- Given a sentence with no extractable financial relationships, when `extract_relationships` is called, then it returns `[]` without raising

### Definition of Done
- [ ] `data/knowledge_graph.py` implemented with `extract_relationships(text)` matching the contract above
- [ ] System prompt instructs the model to extract financial relationships and return a JSON array of `{source, relation, target, confidence}` objects only
- [ ] Markdown fence stripping applied before JSON parse (same pattern as `data/sentiment.py`)
- [ ] `_parse_llm_response` validates per-triple schema and skips invalid triples rather than erroring
- [ ] `confidence` clamped to [0.0, 1.0] per triple
- [ ] Outer `try/except Exception` wrapping the entire function body returns `[]` on any uncaught error
- [ ] `tests/test_knowledge_graph.py` written with Anthropic client mocked — no live API calls
- [ ] Test suite covers: schema (4 keys), happy path triple values, confidence float + range, empty text (no API call), API exception, fence stripping, malformed JSON, invalid triple skipped
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_knowledge_graph.py -v`
- [ ] No new dependencies required (`anthropic` already in `requirements.txt`)

---
