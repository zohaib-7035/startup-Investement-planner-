# Analysis: SEC EDGAR 10-K RAG Ingestion Pipeline
Date: 2026-07-02
Story: 2026-07-02-sec-edgar-10k-rag-ingestion-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline — no web framework, no ORM, no persistence layer. Four existing data modules follow a strict module-per-concern pattern: `data/stock.py` (yfinance market data), `data/sentiment.py` (Anthropic LLM sentiment), `data/screener.py` (pure-Python rule engine), `data/openbb_client.py` (OpenBB SDK company dataset). Key packages already installed: `requests==2.32.4`, `beautifulsoup4==4.13.5`, `lxml==5.4.0` (all pulled in as transitive openbb dependencies — no separate install needed). Missing packages: `chromadb` and `sentence-transformers` (Story 9). No frontend.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| `_safe_float` private helper pattern | `data/stock.py:66`, `data/openbb_client.py` | Returns typed value or `None`; `_clean_html` and `_safe_str` follow the same shape — one input, one safe output or None |
| Outer `try/except Exception` boundary | All 4 existing modules | Every public function's top-level safety net; returns fallback `.copy()` on total failure |
| Module-level fallback constant | `data/sentiment.py`, `data/openbb_client.py` | `_EMPTY_DATASET`, `_API_FAILURE_FALLBACK` — canonical all-None dicts returned via `.copy()`. `_EMPTY_FILING` follows this pattern |
| Per-field inner `try/except` | `data/stock.py:90–95`, `data/openbb_client.py:62–101` | Isolates individual call failures; same pattern needed for each EDGAR API call (CIK lookup, submissions fetch, document download) |
| HTTP mock pattern | `tests/test_stock.py`, `tests/test_openbb_client.py` | `patch("data.<module>.<lib>", mock)` at module level; same approach for `requests.get` in `test_edgar_client.py` |
| `_SECTION_PATTERNS` concept | Not present — new | Will be the first module-level mapping constant that maps to string labels rather than numeric values |
| `requests` library | Transitive dependency via `openbb` | `requests==2.32.4` is installed; can be imported directly in `data/edgar_client.py` without a new pip install |
| `beautifulsoup4` / `lxml` | Transitive dependency via `openbb-sec` | `bs4==4.13.5` and `lxml==5.4.0` are installed; ready to use in `_clean_html` |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/edgar_client.py` | New module | Does not exist — entirely new file |
| `download_10k(ticker)` | Public function | Entry point for Story 7; calls SEC EDGAR API chain |
| `_EMPTY_FILING` | Module-level constant | 5-key all-None fallback dict |
| `_clean_html(raw_html)` | Private helper | Strips HTML tags, normalises whitespace; uses BeautifulSoup + lxml parser |
| SEC EDGAR API chain | External HTTP flow | 3-step: (1) ticker → CIK lookup via `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=10-K&dateb=&owner=include&count=1&output=atom`, (2) parse accession number and filing date, (3) construct and download primary document URL |
| `SEC_USER_AGENT` | Env variable | Required by SEC EDGAR fair-access policy; format: `"Company Name admin@example.com"` |
| `data/chunker.py` | New module | Does not exist — entirely new file |
| `chunk_filing(text, max_chars)` | Public function | Entry point for Story 8; pure Python, no external calls |
| `_SECTION_PATTERNS` | Module-level dict | Maps EDGAR item codes to human-readable names; must cover 10-K standard items: ITEM 1 → Business, ITEM 1A → Risk Factors, ITEM 1B → Unresolved Staff Comments, ITEM 2 → Properties, ITEM 3 → Legal Proceedings, ITEM 7 → MD&A, ITEM 7A → Quantitative Disclosures, ITEM 8 → Financial Statements, ITEM 9 → Changes in Accountants, ITEM 9A → Controls and Procedures |
| `_split_by_paragraphs(text, max_chars)` | Private helper | Splits oversized text at double-newline boundaries; returns list of str |
| `data/vector_store.py` | New module | Does not exist — entirely new file |
| `ingest_chunks(chunks, filing_meta)` | Public function | Entry point for Story 9; calls ChromaDB and embedding model |
| `_build_collection_name(company, filing_type)` | Private helper | Produces `"apple_10k"` style names; lowercase + underscores, no special chars |
| `chromadb` package | New dependency | Not installed — must add to `requirements.txt` at pinned version |
| `sentence-transformers` package | New dependency | Not installed — must add to `requirements.txt` at pinned version; provides local embeddings with no additional API key |
| `CHROMA_PERSIST_DIR` | Env variable | Directory where ChromaDB stores its on-disk vector index |
| `tests/test_edgar_client.py` | New test file | All `requests.get` calls mocked |
| `tests/test_chunker.py` | New test file | No mocking — pure Python function |
| `tests/test_vector_store.py` | New test file | ChromaDB client and embedding model mocked |

---

## Strategic Approach

### Story 7 — edgar_client
Follow the same module-per-concern pattern as `data/openbb_client.py`. The EDGAR retrieval uses a 3-step HTTP chain: ticker → CIK (EDGAR company search), CIK → latest 10-K accession number (EDGAR submissions JSON at `https://data.sec.gov/submissions/CIK{padded_cik}.json`), accession number → primary document download. Each step is wrapped in its own `try/except` block so a CIK lookup failure immediately returns the all-None fallback without attempting subsequent calls. `_clean_html` delegates to BeautifulSoup with the `lxml` parser — both are already installed as openbb transitive deps, so no new pip installs are needed for Story 7.

### Story 8 — chunker
Pure-Python module with no external calls — follows `data/screener.py`'s pattern of zero mocking in tests. `_SECTION_PATTERNS` is a module-level dict rather than a fallback dict; it maps regex-matched item codes to section names. The main function uses `re.split` on `_SECTION_PATTERNS` keys to identify section boundaries, then calls `_split_by_paragraphs` on any section whose character count exceeds `max_chars`.

### Story 9 — vector_store
ChromaDB's persistent client is the local vector store; `sentence-transformers` provides local embeddings with no API key. The idempotency rule (re-ingestion must not duplicate) is achieved by using stable document IDs derived from `{accession_number}_{chunk_id}` and calling ChromaDB's `upsert` rather than `add`. The embedding model is loaded once at module level so repeat calls don't reload it.

---

## Key Design Decisions

- **EDGAR submissions JSON API over full-text search:** `https://data.sec.gov/submissions/CIK{padded}.json` returns a structured list of all filings including accession numbers and dates — more reliable than the EDGAR full-text search index which is optimised for keyword search, not programmatic traversal. The ticker-to-CIK mapping uses the EDGAR company lookup API.

- **`requests` used directly, not via openbb:** `data/edgar_client.py` imports `requests` directly for the EDGAR HTTP calls. This avoids creating a dependency on openbb's internal HTTP client and keeps the module self-contained. Since `requests==2.32.4` is already installed, no new package is needed.

- **BeautifulSoup + lxml for HTML cleaning (not regex):** Regex-based HTML stripping breaks on malformed tags common in older EDGAR filings (pre-2017). BeautifulSoup with the lxml parser handles malformed HTML gracefully. Both are already installed via openbb-sec.

- **`sentence-transformers` over OpenAI embeddings:** The project already uses Anthropic for sentiment (Story 3). Adding an OpenAI dependency would introduce a third LLM provider API key. `sentence-transformers` runs locally with no key, consistent with the pipeline's preference for yfinance-as-default (no Hub key) in Story 6. The `all-MiniLM-L6-v2` model is fast and produces good general-purpose embeddings.

- **ChromaDB upsert with stable IDs for idempotency:** Document IDs are set to `f"{accession_number}_{chunk_id}"`. ChromaDB's `upsert` replaces existing documents with the same ID, preventing count inflation on re-ingestion. This is the only way to satisfy the "re-ingestion must not duplicate" AC without first deleting the collection.

- **Embedding model loaded at module level:** `SentenceTransformer(MODEL_NAME)` is loaded once when `data/vector_store.py` is first imported. Tests must mock this at the module level (same as `obb` in `test_openbb_client.py`) to avoid the ~400MB model download during the test suite.

- **`SEC_USER_AGENT` as env variable:** EDGAR's fair-access policy requires a `User-Agent` header with a contact email. Hardcoding an email violates the no-hardcoded-values norm. The value is read from `os.environ.get("SEC_USER_AGENT", "stock-analyzer contact@example.com")` with a safe default so tests don't fail if the env var is not set.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| EDGAR rate limiting (10 req/sec policy) | High | The 3-step HTTP chain makes 3 requests per `download_10k` call. In a tight loop this could trigger a 429. Add a small `time.sleep(0.11)` between calls, or use a retry with exponential backoff. Not in scope for this story but must be noted. |
| EDGAR `submissions.json` format drift | High | The submissions JSON schema is stable but undocumented. The `filings.recent` key contains filing arrays; the index of the latest 10-K is found by scanning the `form` array for `"10-K"`. If the structure changes, the function falls back to the all-None dict via the exception boundary. |
| 10-K primary document is not always `.htm` | High | Some filings use `.txt` (SGML) or `.htm` with inline XBRL. The primary document must be identified from the filing index page (`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`), not assumed. Parsing the index page adds a 4th HTTP call. |
| Section headers vary in capitalisation and punctuation | Medium | "ITEM 1A." vs "Item 1a." vs "ITEM 1A -" are all valid in real filings. `_SECTION_PATTERNS` regex must use case-insensitive matching and allow optional trailing punctuation (period, dash, colon). |
| `sentence-transformers` first run downloads model (~90MB for MiniLM) | Medium | The `all-MiniLM-L6-v2` model is downloaded on first use if not cached. Tests must mock the model at the module level to avoid network calls and the download delay. |
| ChromaDB persistent client directory | Medium | If `CHROMA_PERSIST_DIR` is not set or the path is not writable, ChromaDB raises on client instantiation. The outer `try/except` in `ingest_chunks` catches this and returns the error fallback. `.env.example` must document the variable. |
| Very large 10-K filings (500K+ chars) | Medium | Some 10-K filings are extremely long. ChromaDB's `upsert` with 1,000+ vectors in a single batch may be slow. Not in scope for this story (batch optimisation is deferred) but chunking may produce more chunks than expected. |
| `text length > 10,000` AC is environment-sensitive | Low | The text-length AC in Story 7 cannot be tested without a real EDGAR download. Tests must mock the HTTP responses and return synthetic text that satisfies the length condition in the mock. |
| Python 3.9 compatibility of new packages | Low | `chromadb` and `sentence-transformers` both support Python 3.9. Verify during `pip install` that no 3.10+ syntax is pulled in as a transitive dependency. |

---

## Acceptance Criteria Coverage

### Story 7 — edgar_client

| Criterion | Status | Notes |
|-----------|--------|-------|
| Valid ticker → dict with 5 keys | Needs work | New function; pattern established by `get_company_dataset` |
| `filing_type == "10-K"` and ISO date string | Needs work | Extracted from EDGAR submissions JSON |
| `text` has no HTML tags | Needs work | `_clean_html` using BeautifulSoup handles this |
| `text` length > 10,000 chars | Needs work | Must be asserted on a mocked response with sufficient synthetic text |
| Invalid ticker → all-None, no raise | Supported pattern | `_EMPTY_FILING.copy()` mirrors existing modules |
| Network exception → all-None, no raise | Supported pattern | Outer `try/except Exception` |
| User-Agent header present | Needs work | `SEC_USER_AGENT` env var; assert in test via `mock_get.call_args` |

### Story 8 — chunker

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns non-empty list from valid text | Needs work | New function |
| Each dict has exactly 4 keys | Needs work | Schema test — same style as existing schema tests |
| `chunk_id` sequential from 1 | Needs work | Enforced by enumerate in the main function |
| No chunk exceeds `max_chars` | Needs work | `_split_by_paragraphs` enforces this |
| ITEM 1A → "Risk Factors", ITEM 7 → "MD&A" | Needs work | `_SECTION_PATTERNS` dict lookup |
| Oversized section splits at paragraph boundary | Needs work | `_split_by_paragraphs` splits on `\n\n` |
| Empty / None input → `[]`, no raise | Needs work | Guard at function entry; no precedent for list-returning fallback in existing modules |
| Never raises | Needs work | Outer `try/except` returning `[]` (not a dict fallback — first in the pipeline) |

### Story 9 — vector_store

| Criterion | Status | Notes |
|-----------|--------|-------|
| Returns dict with 3 keys | Needs work | New function |
| `chunks_inserted` == len(input), `status == "ok"` | Needs work | Asserted against mock ChromaDB upsert count |
| Metadata fields present after ingestion | Needs work | Requires mocked ChromaDB query to verify stored metadata |
| Empty list → 0 inserted, "ok", no raise | Needs work | Guard at function entry |
| Exception → `{chunks_inserted: 0, collection_name: None, status: "error"}` | Supported pattern | Outer `try/except` |
| Re-ingestion does not duplicate | Needs work | ChromaDB `upsert` with `{accession_number}_{chunk_id}` as document ID |

---

## Dependencies

- `data/edgar_client.py` → `requests==2.32.4` (already installed), `beautifulsoup4==4.13.5` (already installed), `lxml==5.4.0` (already installed); no new pip installs for Story 7
- `data/chunker.py` → Python stdlib only (`re`, `typing`); zero new dependencies for Story 8
- `data/vector_store.py` → `chromadb` (not installed — add to `requirements.txt`), `sentence-transformers` (not installed — add to `requirements.txt`); two new installs for Story 9
- `requirements.txt` → must add `requests`, `beautifulsoup4`, `lxml` as explicit entries (currently implicit transitive deps of openbb; pinning them directly removes the hidden dependency)
- `.env.example` → add `SEC_USER_AGENT` (Story 7) and `CHROMA_PERSIST_DIR` (Story 9)
- `data/stock.py`, `data/sentiment.py`, `data/screener.py`, `data/openbb_client.py` — no changes required; new modules are fully independent
