# Analysis: Supply Chain Impact Analysis
Date: 2026-07-02
Story: 2026-07-02-supply-chain-impact-analysis-story.md
Scope: BE-only
Repos scanned: Z:\claude\stock_analyzer (local)

---

## Project Fingerprint

Pure Python 3.9.12 pipeline with eleven data modules at `Z:\claude\stock_analyzer\data\`. This story introduces the pipeline's first purely algorithmic module — no LLM call, no external library, no network I/O. The only dependency is Python's standard library (`collections.deque` for BFS). The closest structural templates are `data/chunker.py` (pure algorithmic logic with outer exception boundary and `[]` fallback) and `tests/test_chunker.py` (plain pytest functions, module-level fixture constants, zero mocking). The story consumes the output schema of `data/knowledge_graph.extract_relationships` as its graph input format, establishing a natural pipeline composition point — but `graph_reasoning.py` must not import from `knowledge_graph.py`.

---

## Domain Concepts

### Existing in Codebase

| Concept | Location | Notes |
|---------|----------|-------|
| Outer `try/except Exception` boundary returning a safe fallback | `data/chunker.py:43–86` | Pattern for algorithmic functions — catches any uncaught error and returns the safe empty result |
| `if not text` input guard at function entry | `data/chunker.py:44–45` | Pattern for early-return on invalid/empty input — Story 13 replicates for empty/whitespace disrupted_entity and empty graph |
| Module-level fixture constants for pure-Python tests | `tests/test_chunker.py:3–11` | `_SAMPLE_TEXT` and `_LONG_SECTION` as named constants — Story 13 test uses the same pattern for `_GRAPH` and `_CYCLIC_GRAPH` fixtures |
| Plain pytest functions with no mocking | `tests/test_chunker.py` and `tests/test_screener.py` | Direct function calls + assertions, no `@patch`, no `MagicMock`, no `sys.modules` — Story 13 test follows the same structure |

### Missing or Needs to Be Added

| Concept | Type | Notes |
|---------|------|-------|
| `data/graph_reasoning.py` | New module | Does not exist; owns Story 13 entirely |
| `analyze_impact(graph, disrupted_entity)` | Public function | BFS traversal + classification + reasoning chain construction |
| Adjacency list builder | Internal helper | Converts the flat triple list into a `{source: [(relation, target)]}` mapping for O(1) neighbour lookup during BFS |
| BFS traversal with path tracking | Internal logic | `collections.deque`-based BFS; `visited` dict records `{node: (depth, parent_node, relation_used)}` per node so the reasoning chain can be reconstructed by walking parent pointers |
| Reasoning chain constructor | Internal logic | For depth-1 nodes: "X is directly affected: {disrupted} is a {RELATION} to X." For depth≥2 nodes: "X is indirectly affected via {intermediary}: {disrupted} is a {R1} to {intermediary}, and {intermediary} is a {R2} to X." (Full multi-hop path description for chains longer than 2 hops.) |
| `_EMPTY_RESULT(disrupted_entity)` factory | Module-level helper | Returns the 5-key safe fallback dict with the caller-supplied disrupted_entity value, empty lists, and total_affected=0 — used at all failure points |
| `tests/test_graph_reasoning.py` | New test file | Pure pytest functions; no mocking; no sys.modules injection |

---

## Strategic Approach

`data/graph_reasoning.py` is the pipeline's first pure graph algorithm — the implementation approach is BFS with parent-pointer tracking. In the first pass, build an adjacency list from the validated triples in O(n). In the second pass, run BFS from `disrupted_entity` using `collections.deque`, recording for each visited node its depth (1 = direct, ≥2 = indirect), its parent node, and the relation used to reach it. After BFS completes, walk the `visited` dict to populate `directly_affected`, `indirectly_affected`, and `reasoning_chain` in discovery order. The parent-pointer approach avoids a separate path-reconstruction pass — for any node, the full ancestry is retrievable by following parent pointers back to the root, which produces the path description needed for the reasoning chain. Cycle safety comes for free from BFS: the `visited` set prevents any node from being enqueued twice.

The test file follows `tests/test_chunker.py` exactly — plain pytest functions, named module-level graph fixtures, direct assertions — no mocking, no decorators, no class hierarchy. The pure-Python nature of the module means every test runs in under 1ms.

---

## Key Design Decisions

- **BFS over DFS for classification correctness:** DFS could visit a node via a longer path before a shorter one, incorrectly classifying a directly-affected entity (depth 1) as indirectly affected (depth 2+). BFS guarantees each node is first reached via the shortest path, so depth-1 classification is always correct.

- **Parent-pointer tracking alongside depth:** Standard BFS only tracks visited/unvisited. Recording `{node: (depth, parent, relation)}` in a single `visited` dict adds no algorithmic overhead but makes reasoning chain construction trivial — walk back from any node to root by following parent pointers, collecting `(node, relation)` pairs for the path description.

- **Adjacency list built from validated triples only:** The graph input may contain malformed triples (missing keys, non-string values). The adjacency builder skips any triple that fails validation — the same skip-invalid pattern used in `data/knowledge_graph._parse_llm_response`. Only clean edges enter the adjacency list; the BFS never sees malformed data.

- **`_EMPTY_RESULT(disrupted_entity)` as a factory function, not a module-level constant:** Unlike prior modules where fallback constants have a fixed schema (e.g. `_EMPTY_ANSWER`), the safe fallback here must carry the caller-supplied `disrupted_entity` string. A zero-argument module-level constant cannot hold a caller value — a one-argument factory returns the correctly populated 5-key dict at every failure point.

- **No relation-type filtering during traversal:** The BFS follows all directed edges regardless of relation type (SUPPLIER, CUSTOMER, PARTNER, etc.). This is intentional — if TSMC is disrupted, a CUSTOMER relationship is also a dependency that propagates impact. Filtering by relation type would require a caller-supplied whitelist that is out of scope for this story.

- **`total_affected` is computed, not stored separately:** After BFS, `total_affected = len(directly_affected) + len(indirectly_affected)`. It is never tracked as a mutable counter during traversal — computing it from the final lists is simpler and guarantees the arithmetic AC is trivially satisfied.

---

## Risks and Edge Cases

| Risk | Severity | Notes |
|------|----------|-------|
| Cycles in the graph cause infinite traversal | High | Mitigated by BFS visited-set — each node is enqueued at most once; a cycle A→B→C→A is handled correctly: A is the start, B and C are visited and added to results, A is already visited when C→A is processed so it is skipped |
| `disrupted_entity` string case mismatch (e.g. "tsmc" vs "TSMC") | Medium | The adjacency list keys come from the `source` field of triples exactly as written; if the caller passes a differently-cased entity name, no matches are found and `[]` is returned. The function must not normalise case — callers are responsible for passing the correct name. Document this in the story, not in code |
| Graph with multiple edges between the same two entities | Low | BFS visits each target node once; duplicate edges between A and B are harmless — B is visited via the first edge, and subsequent edges to B are skipped because B is already in the visited set. The relation used in the reasoning chain will be whichever edge BFS processes first |
| Disrupted entity appears only as a target, never as a source | Low | If `disrupted_entity` is in the graph as a target (someone supplies to it) but never as a source (it supplies nothing), the adjacency list has no entry for it and BFS produces zero results — correct behaviour; `total_affected` is 0 |
| Very large graph with many hops | Low | BFS is O(V+E) — linear in nodes and edges. For the scale of a financial knowledge graph derived from SEC filings (hundreds of companies, thousands of edges at most), performance is not a concern |

---

## Acceptance Criteria Coverage

| Criterion | Status | Notes |
|-----------|--------|-------|
| TSMC graph: directly_affected=[NVIDIA,AMD], indirectly_affected=[Microsoft], total_affected=3 | Needs work | New function; BFS with depth tracking delivers this exactly |
| reasoning_chain has 3 entries; Microsoft entry references NVIDIA | Needs work | Parent-pointer walk from Microsoft → NVIDIA → TSMC builds the path description |
| Returned dict has exactly 5 keys | Needs work | New function; schema fixed in `_EMPTY_RESULT` factory and BFS result assembly |
| Entity not in graph → all-empty fallback, no raise | Supported pattern | BFS starts from `disrupted_entity`; if no edges exist, `visited` stays empty; result is the fallback shape with empty lists |
| Empty graph → fallback, no raise | Supported pattern | Adjacency list builder produces empty dict; BFS never runs; fallback returned |
| Malformed triple skipped, valid triples still processed | Needs work | Adjacency builder validates each triple before adding — skip-invalid pattern identical to `knowledge_graph._parse_llm_response` |
| Cycle → B and C affected, no infinite loop | Supported pattern | BFS visited-set prevents re-enqueueing; cycle termination is a property of BFS, not a special case |
| total_affected == len(directly_affected) + len(indirectly_affected) | Supported pattern | Computed as sum of the two lists after BFS — cannot diverge |

---

## Dependencies

- `data/graph_reasoning.py` → Python standard library only (`collections.deque`) — zero new installs
- `data/knowledge_graph.py` → produces the triple format consumed by `graph_reasoning.py` as `graph` input; no import dependency — caller wires them together
- All existing modules (`stock.py`, `screener.py`, `sentiment.py`, `openbb_client.py`, `edgar_client.py`, `chunker.py`, `vector_store.py`, `rag_query.py`, `rag_answer.py`, `knowledge_graph.py`) — no changes required
- `requirements.txt` — no changes needed
- `.env.example` — no changes needed
