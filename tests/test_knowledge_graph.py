import json
from unittest.mock import patch, MagicMock

from data.knowledge_graph import extract_relationships

_TEXT = "NVIDIA relies heavily on TSMC for manufacturing advanced AI chips."

_VALID_RESPONSE = json.dumps([
    {"source": "NVIDIA", "relation": "SUPPLIER", "target": "TSMC", "confidence": 0.95},
    {"source": "NVIDIA", "relation": "CUSTOMER", "target": "Apple",  "confidence": 0.72},
])

_FENCED_RESPONSE = f"```json\n{_VALID_RESPONSE}\n```"

_MALFORMED_RESPONSE = "NVIDIA and TSMC have a close relationship involving chip manufacturing."

_MIXED_VALIDITY_RESPONSE = json.dumps([
    {"source": "NVIDIA", "relation": "SUPPLIER", "target": "TSMC",    "confidence": 0.95},
    {"source": "NVIDIA", "relation": "PARTNER",  "target": "Samsung"},  # missing confidence
])


def _mock_post(response_text: str):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": response_text}}
    return mock_resp


@patch("data.knowledge_graph.requests.post")
def test_schema_has_four_keys(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = extract_relationships(_TEXT)
    assert len(result) > 0
    assert set(result[0].keys()) == {"source", "relation", "target", "confidence"}


@patch("data.knowledge_graph.requests.post")
def test_happy_path_triple_values(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = extract_relationships(_TEXT)
    first = result[0]
    assert first["source"] == "NVIDIA"
    assert isinstance(first["relation"], str)
    assert first["target"] == "TSMC"
    assert first["confidence"] == 0.95


@patch("data.knowledge_graph.requests.post")
def test_confidence_is_float_in_range(mock_post):
    mock_post.return_value = _mock_post(_VALID_RESPONSE)
    result = extract_relationships(_TEXT)
    for triple in result:
        assert isinstance(triple["confidence"], float)
        assert 0.0 <= triple["confidence"] <= 1.0


@patch("data.knowledge_graph.requests.post")
def test_empty_text_returns_empty_list_without_api_call(mock_post):
    result = extract_relationships("")
    assert result == []
    mock_post.assert_not_called()


@patch("data.knowledge_graph.requests.post")
def test_whitespace_text_returns_empty_list_without_api_call(mock_post):
    result = extract_relationships("   \n\t  ")
    assert result == []
    mock_post.assert_not_called()


@patch("data.knowledge_graph.requests.post")
def test_ollama_unavailable_returns_empty_list(mock_post):
    mock_post.side_effect = RuntimeError("connection refused")
    result = extract_relationships(_TEXT)
    assert result == []


@patch("data.knowledge_graph.requests.post")
def test_fence_stripping_parses_correctly(mock_post):
    mock_post.return_value = _mock_post(_FENCED_RESPONSE)
    result = extract_relationships(_TEXT)
    assert len(result) > 0
    assert result[0]["source"] == "NVIDIA"
    assert result[0]["target"] == "TSMC"


@patch("data.knowledge_graph.requests.post")
def test_malformed_json_returns_empty_list(mock_post):
    mock_post.return_value = _mock_post(_MALFORMED_RESPONSE)
    result = extract_relationships(_TEXT)
    assert result == []


@patch("data.knowledge_graph.requests.post")
def test_invalid_triple_skipped_valid_triple_preserved(mock_post):
    mock_post.return_value = _mock_post(_MIXED_VALIDITY_RESPONSE)
    result = extract_relationships(_TEXT)
    assert len(result) == 1
    assert result[0]["source"] == "NVIDIA"
    assert result[0]["target"] == "TSMC"
    assert result[0]["confidence"] == 0.95
