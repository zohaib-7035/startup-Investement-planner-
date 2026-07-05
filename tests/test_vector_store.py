import sys
from unittest.mock import MagicMock, patch, call

# Prevent sentence_transformers and chromadb from loading their heavy dependencies
# at module import time — the model (~90 MB) must not download during the test suite.
sys.modules.setdefault("sentence_transformers", MagicMock())
sys.modules.setdefault("chromadb", MagicMock())

from data.vector_store import ingest_chunks  # noqa: E402
import data.vector_store as _vs_mod  # noqa: E402

_FILING_META = {
    "company": "Apple Inc.",
    "filing_date": "2023-11-03",
    "filing_type": "10-K",
    "accession_number": "0000320193-23-000106",
}

_CHUNKS = [
    {"chunk_id": 1, "section_name": "Business", "content": "Apple makes consumer devices.", "char_count": 29},
    {"chunk_id": 2, "section_name": "Risk Factors", "content": "Competition is intense.", "char_count": 23},
]


def _make_mocks(num_chunks=2):
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [[0.1, 0.2, 0.3]] * num_chunks

    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection

    return mock_model, mock_client, mock_collection


def test_schema_has_three_keys():
    mock_model, mock_client, _ = _make_mocks()
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        result = ingest_chunks(_CHUNKS, _FILING_META)
    assert set(result.keys()) == {"chunks_inserted", "collection_name", "status"}


def test_happy_path_count_and_status():
    mock_model, mock_client, _ = _make_mocks()
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        result = ingest_chunks(_CHUNKS, _FILING_META)
    assert result["chunks_inserted"] == len(_CHUNKS)
    assert result["status"] == "ok"


def test_upsert_called_not_add():
    mock_model, mock_client, mock_collection = _make_mocks()
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        ingest_chunks(_CHUNKS, _FILING_META)
    mock_collection.upsert.assert_called_once()
    mock_collection.add.assert_not_called()


def test_metadata_fields_passed_to_upsert():
    mock_model, mock_client, mock_collection = _make_mocks()
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        ingest_chunks(_CHUNKS, _FILING_META)
    _, kwargs = mock_collection.upsert.call_args
    metadatas = kwargs["metadatas"]
    required_keys = {"company", "filing_date", "filing_type", "chunk_id", "section_name"}
    for meta in metadatas:
        assert required_keys.issubset(set(meta.keys()))


def test_empty_chunks_returns_zero_inserted():
    mock_model, mock_client, _ = _make_mocks(num_chunks=0)
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        result = ingest_chunks([], _FILING_META)
    assert result["chunks_inserted"] == 0
    assert result["status"] == "ok"


def test_chromadb_exception_returns_error():
    mock_model, _, _ = _make_mocks()
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", side_effect=Exception("ChromaDB unavailable")):
        result = ingest_chunks(_CHUNKS, _FILING_META)
    assert result["chunks_inserted"] == 0
    assert result["collection_name"] is None
    assert result["status"] == "error"


def test_embedding_exception_returns_error():
    mock_model, mock_client, _ = _make_mocks()
    mock_model.encode.side_effect = RuntimeError("model inference failed")
    with patch.object(_vs_mod, "_MODEL", mock_model), \
         patch("data.vector_store.chromadb.PersistentClient", return_value=mock_client):
        result = ingest_chunks(_CHUNKS, _FILING_META)
    assert result["chunks_inserted"] == 0
    assert result["collection_name"] is None
    assert result["status"] == "error"
