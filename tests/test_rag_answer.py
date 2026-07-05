import json
from unittest.mock import patch, MagicMock

from data.rag_answer import answer_from_chunks

_QUESTION = "What did Apple report for revenue in Q1 2025?"

_CHUNKS = [
    {
        "content": "Apple reported total net sales of $119.6 billion for Q1 2025.",
        "section_name": "MD&A",
        "company": "Apple Inc.",
        "filing_date": "2025-01-31",
        "filing_type": "10-K",
        "chunk_id": 5,
        "score": 0.12,
    },
    {
        "content": "Revenue growth was driven primarily by iPhone sales in international markets.",
        "section_name": "Business",
        "company": "Apple Inc.",
        "filing_date": "2025-01-31",
        "filing_type": "10-K",
        "chunk_id": 3,
        "score": 0.25,
    },
]

_VALID_RESPONSE = json.dumps({
    "answer": "Apple reported total net sales of $119.6 billion for Q1 2025.",
    "confidence_score": 0.85,
    "citations": [
        {
            "section_name": "MD&A",
            "company": "Apple Inc.",
            "filing_date": "2025-01-31",
            "filing_type": "10-K",
            "quote": "Apple reported total net sales of $119.6 billion for Q1 2025.",
        }
    ],
})

_FENCED_RESPONSE = f"```json\n{_VALID_RESPONSE}\n```"

_MALFORMED_RESPONSE = "I think Apple had strong results this quarter without any JSON."

_MISSING_QUOTE_RESPONSE = json.dumps({
    "answer": "Apple reported $119.6B revenue.",
    "confidence_score": 0.8,
    "citations": [
        {
            "section_name": "MD&A",
            "company": "Apple Inc.",
            "filing_date": "2025-01-31",
            "filing_type": "10-K",
            # missing "quote" key
        }
    ],
})


def _mock_post(response_text: str):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": response_text}}
    return mock_resp


@patch("data.rag_answer.requests.post")
def test_schema_has_three_keys(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert set(result.keys()) == {"answer", "confidence_score", "citations"}


@patch("data.rag_answer.requests.post")
def test_happy_path_returns_nonempty_answer(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0
    assert isinstance(result["confidence_score"], float)
    assert isinstance(result["citations"], list)


@patch("data.rag_answer.requests.post")
def test_confidence_score_is_float_in_range(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert isinstance(result["confidence_score"], float)
    assert 0.0 <= result["confidence_score"] <= 1.0


@patch("data.rag_answer.requests.post")
def test_citations_have_required_keys(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    required = {"section_name", "company", "filing_date", "filing_type", "quote"}
    for citation in result["citations"]:
        assert required.issubset(set(citation.keys()))


@patch("data.rag_answer.requests.post")
def test_empty_chunks_returns_empty_answer_without_api_call(mock_post):
    result = answer_from_chunks(_QUESTION, [])
    assert result["answer"] == "No relevant filings found."
    assert result["confidence_score"] == 0.0
    assert result["citations"] == []
    mock_post.assert_not_called()


@patch("data.rag_answer.requests.post")
def test_ollama_unavailable_returns_error_answer(mock_post):
    mock_post.side_effect = RuntimeError("connection refused")
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert result["answer"] == "Error generating answer."
    assert result["confidence_score"] == 0.0
    assert result["citations"] == []


@patch("data.rag_answer.requests.post")
def test_fence_stripping_parses_correctly(mock_post):
    mock_post.return_value = _mock_post(_FENCED_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert result["answer"] != "Error generating answer."
    assert isinstance(result["citations"], list)
    assert len(result["citations"]) > 0


@patch("data.rag_answer.requests.post")
def test_malformed_json_returns_error_answer(mock_post):
    mock_post.return_value = _mock_post(_MALFORMED_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert result["answer"] == "Error generating answer."
    assert result["confidence_score"] == 0.0


@patch("data.rag_answer.requests.post")
def test_citations_missing_key_returns_error_answer(mock_post):
    mock_post.return_value = _mock_post(_MISSING_QUOTE_RESPONSE)
    result = answer_from_chunks(_QUESTION, _CHUNKS)
    assert result["answer"] == "Error generating answer."
    assert result["confidence_score"] == 0.0
