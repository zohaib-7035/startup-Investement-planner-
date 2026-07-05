from data.chunker import chunk_filing

_SAMPLE_TEXT = (
    "Cover Page content.\n\n"
    "ITEM 1A. Risk Factors\n\nCompanies face many operational risks.\n\n"
    "ITEM 7. Management Discussion\n\nRevenue grew significantly this year."
)

_LONG_SECTION = "ITEM 1. Business\n\n" + "\n\n".join(
    [f"Paragraph {i}: " + "x" * 200 for i in range(30)]
)


def test_section_names_detected():
    result = chunk_filing(_SAMPLE_TEXT)
    names = {c["section_name"] for c in result}
    assert "Risk Factors" in names
    assert "MD&A" in names


def test_schema_has_four_keys():
    result = chunk_filing(_SAMPLE_TEXT)
    assert len(result) > 0
    for chunk in result:
        assert set(chunk.keys()) == {"chunk_id", "section_name", "content", "char_count"}


def test_chunk_ids_are_sequential():
    result = chunk_filing(_SAMPLE_TEXT)
    ids = [c["chunk_id"] for c in result]
    assert ids == list(range(1, len(ids) + 1))


def test_max_chars_enforced():
    result = chunk_filing(_LONG_SECTION, max_chars=4000)
    assert len(result) > 0
    for chunk in result:
        assert chunk["char_count"] <= 4000


def test_paragraph_boundary_split():
    long_para_a = "A" * 2500
    long_para_b = "B" * 2500
    text = f"ITEM 1. Business\n\n{long_para_a}\n\n{long_para_b}"
    result = chunk_filing(text, max_chars=4000)
    business_chunks = [c for c in result if c["section_name"] == "Business"]
    assert len(business_chunks) >= 2
    for chunk in business_chunks:
        assert chunk["char_count"] <= 4000


def test_empty_string_returns_empty_list():
    assert chunk_filing("") == []


def test_none_returns_empty_list():
    assert chunk_filing(None) == []
