from data.graph_reasoning import analyze_impact

_GRAPH = [
    {"source": "TSMC", "relation": "SUPPLIER", "target": "NVIDIA"},
    {"source": "TSMC", "relation": "SUPPLIER", "target": "AMD"},
    {"source": "NVIDIA", "relation": "SUPPLIER", "target": "Microsoft"},
]

_CYCLIC_GRAPH = [
    {"source": "A", "relation": "DEPENDENCY", "target": "B"},
    {"source": "B", "relation": "DEPENDENCY", "target": "C"},
    {"source": "C", "relation": "DEPENDENCY", "target": "A"},
]

_MIXED_GRAPH = [
    {"source": "TSMC", "relation": "SUPPLIER", "target": "NVIDIA"},
    {"relation": "SUPPLIER", "target": "Samsung"},
]


def test_schema_has_five_keys():
    result = analyze_impact(_GRAPH, "TSMC")
    assert set(result.keys()) == {
        "disrupted_entity",
        "directly_affected",
        "indirectly_affected",
        "reasoning_chain",
        "total_affected",
    }


def test_direct_and_indirect_classification():
    result = analyze_impact(_GRAPH, "TSMC")
    assert "NVIDIA" in result["directly_affected"]
    assert "AMD" in result["directly_affected"]
    assert "Microsoft" in result["indirectly_affected"]
    assert result["total_affected"] == 3


def test_reasoning_chain_count():
    result = analyze_impact(_GRAPH, "TSMC")
    assert len(result["reasoning_chain"]) == 3


def test_reasoning_chain_microsoft_references_nvidia():
    result = analyze_impact(_GRAPH, "TSMC")
    microsoft_entries = [e for e in result["reasoning_chain"] if "Microsoft" in e]
    assert len(microsoft_entries) == 1
    assert "NVIDIA" in microsoft_entries[0]


def test_entity_not_in_graph_returns_empty():
    result = analyze_impact(_GRAPH, "Apple")
    assert result["directly_affected"] == []
    assert result["indirectly_affected"] == []
    assert result["reasoning_chain"] == []
    assert result["total_affected"] == 0


def test_empty_graph_returns_fallback():
    result = analyze_impact([], "TSMC")
    assert result["directly_affected"] == []
    assert result["total_affected"] == 0


def test_malformed_triple_skipped_valid_processed():
    result = analyze_impact(_MIXED_GRAPH, "TSMC")
    assert "NVIDIA" in result["directly_affected"]
    assert result["total_affected"] == 1


def test_cycle_terminates_without_infinite_loop():
    result = analyze_impact(_CYCLIC_GRAPH, "A")
    assert "B" in result["directly_affected"]
    assert "C" in result["indirectly_affected"]
    assert result["total_affected"] == 2


def test_total_affected_equals_sum_of_lists():
    result = analyze_impact(_GRAPH, "TSMC")
    assert result["total_affected"] == (
        len(result["directly_affected"]) + len(result["indirectly_affected"])
    )
