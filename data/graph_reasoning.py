from collections import deque
from typing import Dict, List


def _EMPTY_RESULT(disrupted_entity: str) -> Dict:
    return {
        "disrupted_entity": disrupted_entity,
        "directly_affected": [],
        "indirectly_affected": [],
        "reasoning_chain": [],
        "total_affected": 0,
    }


def analyze_impact(graph: list, disrupted_entity: str) -> Dict:
    if not isinstance(disrupted_entity, str) or not disrupted_entity.strip():
        return _EMPTY_RESULT(disrupted_entity if isinstance(disrupted_entity, str) else "")
    if not isinstance(graph, list) or not graph:
        return _EMPTY_RESULT(disrupted_entity)
    try:
        # Build adjacency list from validated triples only
        adj: Dict[str, List] = {}
        for item in graph:
            if not isinstance(item, dict):
                continue
            src = item.get("source", "")
            rel = item.get("relation", "")
            tgt = item.get("target", "")
            if not (isinstance(src, str) and src.strip()
                    and isinstance(rel, str) and rel.strip()
                    and isinstance(tgt, str) and tgt.strip()):
                continue
            if src not in adj:
                adj[src] = []
            adj[src].append((rel, tgt))

        # BFS with parent-pointer tracking
        # visited: {node: (depth, parent_node, relation_used)}
        visited: Dict[str, tuple] = {disrupted_entity: (0, None, None)}
        queue: deque = deque([disrupted_entity])

        while queue:
            current = queue.popleft()
            current_depth = visited[current][0]
            for rel, tgt in adj.get(current, []):
                if tgt not in visited:
                    visited[tgt] = (current_depth + 1, current, rel)
                    queue.append(tgt)

        # Classify entities and build reasoning chain in BFS discovery order
        directly_affected: List[str] = []
        indirectly_affected: List[str] = []
        reasoning_chain: List[str] = []

        for node, (depth, parent, rel_used) in visited.items():
            if depth == 0:
                continue

            if depth == 1:
                chain_str = (
                    f"{node} is directly affected: "
                    f"{disrupted_entity} is a {rel_used} to {node}."
                )
                directly_affected.append(node)
            else:
                # Walk parent pointers back to disrupted_entity to reconstruct path
                path_nodes = []
                current_node = node
                while True:
                    _d, par, r = visited[current_node]
                    if par is None:
                        break
                    path_nodes.append((current_node, r, par))
                    current_node = par
                path_nodes.reverse()

                hop_descriptions = [
                    f"{src_node} is a {rel_hop} to {tgt_node}"
                    for tgt_node, rel_hop, src_node in path_nodes
                ]
                path_desc = ", and ".join(hop_descriptions)
                direct_parent = visited[node][1]
                chain_str = (
                    f"{node} is indirectly affected via {direct_parent}: "
                    f"{path_desc}."
                )
                indirectly_affected.append(node)

            reasoning_chain.append(chain_str)

        return {
            "disrupted_entity": disrupted_entity,
            "directly_affected": directly_affected,
            "indirectly_affected": indirectly_affected,
            "reasoning_chain": reasoning_chain,
            "total_affected": len(directly_affected) + len(indirectly_affected),
        }
    except Exception:
        return _EMPTY_RESULT(disrupted_entity)
