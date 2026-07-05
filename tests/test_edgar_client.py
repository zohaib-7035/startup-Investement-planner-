import requests
from unittest.mock import patch, MagicMock

from data.edgar_client import download_10k

_TICKER_DATA = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
}

_SUBMISSIONS_DATA = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q"],
            "accessionNumber": ["0000320193-23-000106", "0000320193-23-000100"],
            "filingDate": ["2023-11-03", "2023-08-04"],
        }
    },
}

_INDEX_HTML = (
    '<table class="tableFile">'
    "<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th></tr>"
    "<tr><td>1</td><td>Annual Report</td>"
    '<td><a href="/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm">'
    "aapl-20230930.htm</a></td>"
    "<td>10-K</td></tr>"
    "</table>"
)

# HTML primary document long enough that cleaned text exceeds 10,000 chars
_PRIMARY_HTML = "<html><body><p>" + ("Apple Inc annual report text content. " * 600) + "</p></body></html>"


def _json_resp(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


def _text_resp(text):
    m = MagicMock()
    m.text = text
    m.raise_for_status.return_value = None
    return m


def _happy_side_effects():
    return [
        _json_resp(_TICKER_DATA),
        _json_resp(_SUBMISSIONS_DATA),
        _text_resp(_INDEX_HTML),
        _text_resp(_PRIMARY_HTML),
    ]


@patch("data.edgar_client.requests.get")
def test_schema_has_five_keys(mock_get):
    mock_get.side_effect = _happy_side_effects()
    result = download_10k("AAPL")
    assert set(result.keys()) == {"text", "filing_date", "filing_type", "company", "accession_number"}


@patch("data.edgar_client.requests.get")
def test_happy_path_field_values(mock_get):
    mock_get.side_effect = _happy_side_effects()
    result = download_10k("AAPL")
    assert result["filing_type"] == "10-K"
    assert result["filing_date"] == "2023-11-03"
    assert result["company"] == "Apple Inc."
    assert result["text"] is not None
    assert "<" not in result["text"]
    assert ">" not in result["text"]
    assert len(result["text"]) > 10000


@patch("data.edgar_client.requests.get")
def test_user_agent_header_in_all_calls(mock_get):
    mock_get.side_effect = _happy_side_effects()
    download_10k("AAPL")
    assert mock_get.call_count > 0
    for call in mock_get.call_args_list:
        headers = call.kwargs.get("headers", {})
        assert "User-Agent" in headers
        assert "@" in headers["User-Agent"]


@patch("data.edgar_client.requests.get")
def test_invalid_ticker_returns_all_none(mock_get):
    mock_get.return_value = _json_resp(_TICKER_DATA)
    result = download_10k("INVALID_XYZ")
    assert all(v is None for v in result.values())


@patch("data.edgar_client.requests.get")
def test_network_exception_returns_all_none(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("network error")
    result = download_10k("AAPL")
    assert all(v is None for v in result.values())
