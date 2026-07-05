# User Story: RAG Query and Grounded Answer
Date: 2026-07-02
Source: Pasted text

---

## Story 10: Retrieve Relevant Filing Chunks from Vector Database

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that embeds a natural language question and retrieves the most semantically relevant filing chunks from the vector database,
**So that** downstream answer synthesis has a grounded, evidence-based context to work from without requiring any LLM involvement in the retrieval step.

### Scope In
- Accept a question string, a collection name string, and an optional `n_results` integer (default 5) as input
- Embed the question using the same `sentence-transformers` model used during ingestion (`all-MiniLM-L6-v2`) to ensure vector space alignment
- Query ChromaDB's persistent collection using the embedded question vector
- Return a list of dicts, each containing the chunk's content and all five metadata fields: `section_name`, `company`, `filing_date`, `filing_type`, `chunk_id`; also include a `score` field (float, the cosine distance from ChromaDB) so callers can filter by relevance threshold
- Return `[]` on any failure (collection not found, model error, empty collection, any exception)
- Live in `data/rag_query.py` as `retrieve_chunks(question: str, collection_name: str, n_results: int = 5) -> list[dict]`
- Reuse the module-level `_MODEL` from `data/vector_store.py` concept — load the sentence-transformer model once at module level in `rag_query.py` (do not import from `vector_store.py`; models are loaded independently per module per the no-cross-module-import rule)
- Use the same `CHROMA_PERSIST_DIR` env variable to locate the ChromaDB persistent client

### Scope Out
- No answer generation or LLM calls — pure vector retrieval only
- No ranking, re-ranking, or post-filtering of results beyond ChromaDB's built-in similarity search
- No cross-collection search — caller supplies a single collection name; multi-collection fan-out is a separate story
- No streaming or pagination — return all `n_results` at once
- No caching of embeddings or query results
- No keyword search fallback if semantic search returns no results

### Acceptance Criteria
- **Given** a question string and a valid collection name, **when** `retrieve_chunks(question, collection_name)` is called, **then** it returns a list of dicts
- **Given** a successful retrieval, **when** each dict is inspected, **then** it contains exactly seven keys: `content`, `section_name`, `company`, `filing_date`, `filing_type`, `chunk_id`, `score`
- **Given** `n_results=3`, **when** `retrieve_chunks` is called and the collection has at least 3 chunks, **then** at most 3 chunks are returned
- **Given** `score` is inspected on returned chunks, **when** the list is sorted by score ascending, **then** the first chunk is the most semantically similar to the question (lower distance = higher similarity)
- **Given** a collection that does not exist or is empty, **when** `retrieve_chunks` is called, **then** it returns `[]` and does not raise
- **Given** the ChromaDB client or the embedding model raises any exception, **when** `retrieve_chunks` is called, **then** it returns `[]` and does not raise

### Definition of Done
- [ ] `data/rag_query.py` implemented with `retrieve_chunks(question, collection_name, n_results)` matching the contract above
- [ ] Module-level `_MODEL = SentenceTransformer(MODEL_NAME)` loaded once on import
- [ ] Module-level `_EMPTY_RESULTS = []` used as the fallback return value
- [ ] Outer `try/except Exception` wrapping the entire function body
- [ ] `tests/test_rag_query.py` written with `_MODEL` and `chromadb.PersistentClient` mocked at module level
- [ ] Test suite covers: schema test (7 keys), n_results enforcement, score field is float, empty collection returns [], exception returns []
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_rag_query.py -v`
- [ ] No new dependencies required (`sentence-transformers` and `chromadb` already in `requirements.txt`)

---

## Story 11: Generate a Grounded Answer with Citations and Confidence Score

**As a** financial RAG engineer building the investment intelligence pipeline,
**I want** a function that takes a question and a list of retrieved filing chunks and returns a structured JSON-compatible answer with source citations and a confidence score, using only the evidence present in the provided chunks,
**So that** the platform can answer financial questions with full traceability back to the original SEC filings, without hallucinating information not present in the source documents.

### Scope In
- Accept a question string and a list of chunk dicts (output of `retrieve_chunks`) as input
- Call the Anthropic Claude API (Haiku model for speed and cost efficiency) with a system prompt that strictly forbids answering from prior knowledge — the model must answer only from the provided chunk text
- The system prompt must instruct the model to return a JSON object with exactly three fields: `answer` (str), `confidence_score` (float, 0.0–1.0 representing how well the retrieved evidence answers the question), and `citations` (list of dicts, each containing `section_name`, `company`, `filing_date`, `filing_type`, and a `quote` field containing the verbatim excerpt from the chunk that supports the answer)
- Parse the model's JSON response and return the dict; strip markdown fences before parsing (reuse the fence-stripping pattern from `data/sentiment.py`)
- Return a fallback dict `{answer: "No relevant filings found.", confidence_score: 0.0, citations: []}` when the chunks list is empty
- Return the same fallback dict structure with `answer: "Error generating answer."` and `confidence_score: 0.0` on any Anthropic API error or JSON parse failure
- Live in `data/rag_answer.py` as `answer_from_chunks(question: str, chunks: list) -> dict`

### Scope Out
- No vector database access — this function receives chunks already retrieved; it does not call ChromaDB
- No follow-up questions or conversational memory — single-turn Q&A only
- No streaming of the answer
- No token count tracking or cost monitoring
- No re-ranking or filtering of the chunks before passing to the LLM — caller is responsible for providing relevant chunks
- No UI or HTTP endpoint — Python function only
- No support for multi-company or multi-filing aggregation in a single call (the model reasons over whatever chunks are passed in)

### Acceptance Criteria
- **Given** a non-empty chunks list and a question, **when** `answer_from_chunks(question, chunks)` is called, **then** it returns a dict containing exactly three keys: `answer`, `confidence_score`, `citations`
- **Given** a successful API call, **when** `confidence_score` is inspected, **then** it is a Python float between 0.0 and 1.0 inclusive
- **Given** a successful API call, **when** `citations` is inspected, **then** it is a list where each citation dict contains `section_name`, `company`, `filing_date`, `filing_type`, and `quote`
- **Given** an empty chunks list `[]`, **when** `answer_from_chunks` is called, **then** `answer` is `"No relevant filings found."`, `confidence_score` is `0.0`, and `citations` is `[]`, and no exception is raised
- **Given** the Anthropic API raises any exception, **when** `answer_from_chunks` is called, **then** it returns `{answer: "Error generating answer.", confidence_score: 0.0, citations: []}` without raising
- **Given** the API returns a response with markdown fences around the JSON, **when** the response is parsed, **then** the fences are stripped and the JSON is parsed correctly
- **Given** a question about Apple Q1 2025 revenue and chunks containing the relevant MD&A section, **when** `answer_from_chunks` is called, **then** `answer` contains only information present in the provided chunks and `citations` identifies the specific chunk and quote that supports the answer
- **Given** the API returns malformed JSON, **when** `answer_from_chunks` is called, **then** the error fallback dict is returned without raising

### Definition of Done
- [ ] `data/rag_answer.py` implemented with `answer_from_chunks(question, chunks)` matching the contract above
- [ ] System prompt enforces evidence-only answering with explicit "do not use prior knowledge" instruction
- [ ] Markdown fence stripping applied before JSON parse (same pattern as `data/sentiment.py`)
- [ ] `_EMPTY_ANSWER` module-level fallback constant for the no-data case
- [ ] `_ERROR_ANSWER` module-level fallback constant for the API error case
- [ ] Outer `try/except Exception` wrapping the entire function body
- [ ] `tests/test_rag_answer.py` written with Anthropic client mocked
- [ ] Test suite covers: schema test (3 keys), confidence_score float validation, citations keys, empty chunks fallback, Anthropic exception fallback, fence stripping, malformed JSON fallback
- [ ] All tests passing: `& "Z:\python39\python.exe" -m pytest tests/test_rag_answer.py -v`
- [ ] No new dependencies required (`anthropic` already in `requirements.txt`)

---
