# User Story: SEC EDGAR 10-K RAG Ingestion Pipeline
Date: 2026-07-02
Source: Pasted text

---

## Story 1: Download and Extract 10-K Filing Text from SEC EDGAR

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that downloads the latest 10-K filing for a given ticker from SEC EDGAR and returns the cleaned plain text,
**So that** downstream chunking and embedding stages have a single, reliable text source without needing to deal with EDGAR's HTML or XBRL format directly.

### Scope In
- Accept a ticker string (e.g. `"AAPL"`) as input
- Use the SEC EDGAR full-text search API (`https://efts.sec.gov/LATEST/search-index?q=...&dateRange=custom&...&forms=10-K`) or the EDGAR XBRL API to locate the latest 10-K filing for the ticker
- Download the primary document (HTM or HTML) of the filing
- Strip HTML tags, remove boilerplate headers/footers, normalise whitespace, and return clean plain text
- Return a dict containing: `text` (str), `filing_date` (str, ISO format), `filing_type` (str, `"10-K"`), `company` (str), `accession_number` (str)
- Return an all-None fallback dict on any failure (network error, ticker not found, no 10-K available)
- Live in `data/edgar_client.py` as `download_10k(ticker: str) -> dict`
- Use only the public SEC EDGAR API — no authentication required
- Respect EDGAR rate limits: include a `User-Agent` header with a contact email as required by SEC fair-access policy

### Scope Out
- No parsing of XBRL structured data — plain text extraction only
- No support for filing types other than 10-K (10-Q, 8-K, etc. are separate stories)
- No local file caching or persistence of downloaded filings
- No multi-ticker batch downloads
- No section parsing or chunking (Story 2)
- No embedding or vector store operations (Story 3)

### Acceptance Criteria

- **Given** a valid ticker `"AAPL"`, **when** `download_10k("AAPL")` is called, **then** the returned dict contains exactly five keys: `text`, `filing_date`, `filing_type`, `company`, `accession_number`
- **Given** a valid ticker, **when** the EDGAR API returns a filing, **then** `filing_type` is exactly `"10-K"` and `filing_date` is a valid ISO date string (e.g. `"2024-11-01"`)
- **Given** a valid ticker, **when** the filing text is extracted, **then** `text` is a non-empty string containing no raw HTML tags (no `<`, `>`, or `&lt;` sequences)
- **Given** a valid ticker, **when** the filing text is extracted, **then** `text` length is greater than 10,000 characters (a 10-K is always a substantial document)
- **Given** an invalid or unknown ticker (e.g. `"INVALID_XYZ"`), **when** `download_10k` is called, **then** it returns a dict where all five values are `None` and does not raise
- **Given** the EDGAR API or the filing download raises any exception (network error, timeout, HTTP error), **when** `download_10k` is called, **then** it catches the exception and returns the all-None fallback dict without raising
- **Given** any call to `download_10k`, **when** the HTTP request is made, **then** the `User-Agent` header contains a valid contact email as required by SEC EDGAR fair-access policy

### Definition of Done
- [ ] `data/edgar_client.py` implemented with `download_10k(ticker)` matching the contract above
- [ ] `_EMPTY_FILING` module-level constant defines the fallback dict; returned via `.copy()` on error
- [ ] `_clean_html(raw_html)` private helper strips tags and normalises whitespace
- [ ] `tests/test_edgar_client.py` written with all HTTP calls mocked via `unittest.mock.patch`
- [ ] Test suite covers: happy path (all fields present and correct types), HTML-stripped text assertion, invalid ticker, network exception
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_edgar_client.py -v`
- [ ] `requirements.txt` updated with any new dependencies (e.g. `requests` is already available via openbb; `beautifulsoup4` if needed)
- [ ] `.env.example` updated with `SEC_USER_AGENT` if the contact email is stored as an env variable

---

## Story 2: Chunk 10-K Filing Text into Semantic Sections

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that splits a 10-K plain-text filing into labelled semantic chunks,
**So that** each chunk can be independently embedded and retrieved by section, enabling precise answers to questions about specific parts of the filing (e.g. "Risk Factors", "MD&A").

### Scope In
- Accept a text string (output of Story 1's `download_10k`) and a company metadata dict as input
- Detect known 10-K section headings (e.g. "ITEM 1.", "ITEM 1A.", "ITEM 7.", "ITEM 8.") using pattern matching and split the text at each boundary
- Assign a human-readable `section_name` to each chunk (e.g. `"Business"`, `"Risk Factors"`, `"MD&A"`, `"Financial Statements"`)
- Apply a maximum chunk size (configurable, default 1,000 tokens or ~4,000 characters) — split oversized sections by paragraph boundary, not mid-sentence
- Assign a sequential `chunk_id` (integer, 1-indexed) to each chunk within a filing
- Return a list of dicts, each containing: `chunk_id` (int), `section_name` (str), `content` (str), `char_count` (int)
- Return `[]` if the input text is empty or None
- Live in `data/chunker.py` as `chunk_filing(text: str, max_chars: int = 4000) -> list[dict]`
- Pure Python — no LLM calls, no external API calls

### Scope Out
- No semantic similarity-based chunking (LLM-assisted splitting is a future story)
- No deduplication of overlapping chunks
- No embedding generation (Story 3)
- No vector store operations (Story 3)
- No support for filing types other than 10-K section patterns
- No chunking of exhibits or footnotes (main body only)

### Acceptance Criteria

- **Given** a valid 10-K text string, **when** `chunk_filing(text)` is called, **then** it returns a non-empty list of dicts
- **Given** a valid 10-K text, **when** chunks are returned, **then** each dict contains exactly four keys: `chunk_id`, `section_name`, `content`, `char_count`
- **Given** a valid 10-K text, **when** chunks are returned, **then** `chunk_id` values are sequential integers starting at 1 with no gaps
- **Given** a valid 10-K text, **when** chunks are returned, **then** no chunk's `char_count` exceeds `max_chars` (default 4,000)
- **Given** a valid 10-K text containing "ITEM 1A" and "ITEM 7" headings, **when** chunks are returned, **then** at least one chunk has `section_name` matching `"Risk Factors"` and at least one matches `"MD&A"`
- **Given** a text with a section longer than `max_chars`, **when** that section is chunked, **then** the split occurs at a paragraph boundary (double newline), not mid-sentence
- **Given** an empty string or `None` as input, **when** `chunk_filing` is called, **then** it returns `[]` and does not raise
- **Given** any input, **when** `chunk_filing` is called, **then** it never raises — all exceptions are caught and return `[]`

### Definition of Done
- [ ] `data/chunker.py` implemented with `chunk_filing(text, max_chars)` matching the contract above
- [ ] `_SECTION_PATTERNS` module-level dict maps EDGAR item identifiers to human-readable section names
- [ ] `_split_by_paragraphs(text, max_chars)` private helper handles oversized section splitting
- [ ] `tests/test_chunker.py` written — no mocking required (pure Python function)
- [ ] Test suite covers: happy path (known sections detected), chunk_id sequential, max_chars enforcement, paragraph-boundary split, empty input, None input
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_chunker.py -v`
- [ ] No new dependencies required (pure Python stdlib only)

---

## Story 3: Generate Embeddings and Ingest Chunks into Vector Database

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that takes a list of filing chunks and their filing metadata, generates embeddings for each chunk, and stores them in a vector database with full metadata,
**So that** the chunks are retrievable by semantic similarity and filterable by company, filing date, filing type, chunk ID, and section name.

### Scope In
- Accept a list of chunk dicts (output of Story 2's `chunk_filing`) and a filing metadata dict (output of Story 1's `download_10k`) as input
- Generate an embedding vector for each chunk's `content` field using a sentence-transformer or OpenAI embedding model
- Store each chunk in a vector database (ChromaDB as the default local vector store — no cloud service required)
- Each stored vector must carry the following metadata fields: `company` (str), `filing_date` (str), `filing_type` (str), `chunk_id` (int), `section_name` (str)
- Return a confirmation dict: `{chunks_inserted: int, collection_name: str, status: str}`
- Return `{chunks_inserted: 0, collection_name: None, status: "error"}` on any failure
- Live in `data/vector_store.py` as `ingest_chunks(chunks: list, filing_meta: dict) -> dict`
- Use ChromaDB's persistent client so vectors survive process restarts
- Collection name derived from `filing_meta["company"]` and `filing_meta["filing_type"]` (e.g. `"apple_10k"`)

### Scope Out
- No semantic search / query interface (retrieval is a separate story)
- No deduplication — re-ingesting the same filing overwrites existing vectors for that accession number
- No cloud vector database (Pinecone, Weaviate, etc.) — ChromaDB local only for this iteration
- No re-ranking or post-processing of embedding results
- No batch size optimisation for large filings (single-batch ingestion is acceptable for this story)
- No support for multiple embedding providers — one provider is configured and used

### Acceptance Criteria

- **Given** a non-empty list of chunks and valid filing metadata, **when** `ingest_chunks(chunks, filing_meta)` is called, **then** the returned dict contains exactly three keys: `chunks_inserted`, `collection_name`, `status`
- **Given** a non-empty list of chunks, **when** ingestion succeeds, **then** `chunks_inserted` equals the length of the input chunks list and `status` is `"ok"`
- **Given** ingestion succeeds, **when** the ChromaDB collection is queried by `chunk_id` metadata filter, **then** the stored document is retrievable and its metadata contains all five required fields: `company`, `filing_date`, `filing_type`, `chunk_id`, `section_name`
- **Given** an empty chunks list, **when** `ingest_chunks([], filing_meta)` is called, **then** it returns `{chunks_inserted: 0, collection_name: ..., status: "ok"}` and does not raise
- **Given** the vector database or embedding model raises any exception, **when** `ingest_chunks` is called, **then** it catches the exception and returns `{chunks_inserted: 0, collection_name: None, status: "error"}` without raising
- **Given** the same filing is ingested twice, **when** `ingest_chunks` is called the second time, **then** vectors for that filing are replaced (not duplicated) — the total count in the collection does not double

### Definition of Done
- [ ] `data/vector_store.py` implemented with `ingest_chunks(chunks, filing_meta)` matching the contract above
- [ ] ChromaDB persistent client configured with a base directory from `.env` / `CHROMA_PERSIST_DIR` env variable
- [ ] `_build_collection_name(company, filing_type)` private helper produces consistent, filesystem-safe collection names
- [ ] `tests/test_vector_store.py` written with ChromaDB and embedding model calls mocked
- [ ] Test suite covers: happy path (count matches), metadata fields present, empty chunks list, ChromaDB exception, embedding exception
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_vector_store.py -v`
- [ ] `requirements.txt` updated with `chromadb` and embedding package (e.g. `sentence-transformers` or `openai`) at pinned versions
- [ ] `.env.example` updated with `CHROMA_PERSIST_DIR` and any embedding API key variables

---
