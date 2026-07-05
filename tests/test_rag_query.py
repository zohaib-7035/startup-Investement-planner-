import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("sentence_transformers", MagicMock())
sys.modules.setdefault("chromadb", MagicMock())

from data.rag_query import retrieve_chunks  # noqa: E402
import data.rag_query as _rq_mod  # noqa: E402

_QUESTION = "What did Apple report for revenue in Q1 2025?"
_COLLECTION = "apple_inc_10k"

_QUERY_RESULT = {
    "documents": [
        [
            "Apple reported total net sales of $119.6 billion for Q1 2025.",
            "Revenue growth was driven primarily by iPhone sales in international markets.",
        ]
    ],
    "metadatas": [
        [
            {
                "section_name": "MD&A",
                "company": "Apple Inc.",
                "filing_date": "2025-01-31",
                "filing_type": "10-K",
                "chunk_id": 5,
            },
            {
                "section_name": "Business",
                "company": "Apple Inc.",
                "filing_date": "2025-01-31",
                "filing_type": "10-K",
                "chunk_id": 3,
            },
        ]
    ],
    "distances": [[0.12, 0.35]],
}


def _make_mocks():
    mock_model = MagicMock()
    mock_model.encode.return_value.__getitem__.return_value.tolist.return_value = [0.1, 0.2, 0.3]

    mock_collection = MagicMock()
    mock_collection.query.return_value = _QUERY_RESULT

    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection

    return mock_model, mock_client, mock_collection


def test_schema_has_seven_keys():
    mock_model, mock_client, _ = _make_mocks()
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        result = retrieve_chunks(_QUESTION, _COLLECTION)
    assert len(result) > 0
    assert set(result[0].keys()) == {"content", "section_name", "company", "filing_date", "filing_type", "chunk_id", "score"}


def test_happy_path_field_values():
    mock_model, mock_client, _ = _make_mocks()
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        result = retrieve_chunks(_QUESTION, _COLLECTION)
    first = result[0]
    assert first["content"] == "Apple reported total net sales of $119.6 billion for Q1 2025."
    assert first["section_name"] == "MD&A"
    assert first["company"] == "Apple Inc."
    assert first["filing_date"] == "2025-01-31"
    assert first["filing_type"] == "10-K"
    assert first["chunk_id"] == 5
    assert first["score"] == 0.12


def test_score_is_python_float():
    mock_model, mock_client, _ = _make_mocks()
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        result = retrieve_chunks(_QUESTION, _COLLECTION)
    assert isinstance(result[0]["score"], float)


def test_n_results_passed_to_query():
    mock_model, mock_client, mock_collection = _make_mocks()
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        retrieve_chunks(_QUESTION, _COLLECTION, n_results=3)
    _, kwargs = mock_collection.query.call_args
    assert kwargs["n_results"] == 3


def test_missing_collection_returns_empty_list():
    mock_model, mock_client, _ = _make_mocks()
    mock_client.get_collection.side_effect = Exception("Collection not found")
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        result = retrieve_chunks(_QUESTION, _COLLECTION)
    assert result == []


def test_model_exception_returns_empty_list():
    mock_model, mock_client, _ = _make_mocks()
    mock_model.encode.side_effect = RuntimeError("Model failed")
    with patch.object(_rq_mod, "_MODEL", mock_model), \
         patch("data.rag_query.chromadb.PersistentClient", return_value=mock_client):
        result = retrieve_chunks(_QUESTION, _COLLECTION)
    assert result == []
