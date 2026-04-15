from __future__ import annotations

from copy import deepcopy
from typing import Any


class EvidenceGraph:
    def __init__(self, *, nodes: list[dict[str, Any]] | None = None, edges: list[dict[str, Any]] | None = None) -> None:
        self.nodes = [dict(node) for node in (nodes or [])]
        self.edges = [dict(edge) for edge in (edges or [])]
        self._node_counts = _counts_by_type(self.nodes)
        self._edge_count = len(self.edges)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "EvidenceGraph":
        if not isinstance(payload, dict):
            return cls()
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        return cls(
            nodes=nodes if isinstance(nodes, list) else [],
            edges=edges if isinstance(edges, list) else [],
        )

    def add_node(self, node_type: str, payload: dict[str, Any], *, created_by: str) -> str:
        self._node_counts[node_type] = self._node_counts.get(node_type, 0) + 1
        node_id = f"{node_type}:{self._node_counts[node_type]}"
        self.nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "payload": deepcopy(payload),
                "created_by": created_by,
            }
        )
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        *,
        created_by: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        self._edge_count += 1
        edge_id = f"edge:{self._edge_count}"
        self.edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": edge_type,
                "payload": deepcopy(payload or {}),
                "created_by": created_by,
            }
        )
        return edge_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": deepcopy(self.nodes),
            "edges": deepcopy(self.edges),
        }


def initialize_evidence_graph(*, candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    graph = EvidenceGraph()
    candidate_node = graph.add_node("candidate", candidate, created_by="deterministic_evidence_packet")
    for check in evidence.get("deterministic_checks") or evidence.get("falsification_checklist") or []:
        check_node = graph.add_node("deterministic_check", check, created_by="deterministic_evidence_packet")
        graph.add_edge(check_node, candidate_node, "derived_from", created_by="deterministic_evidence_packet")
    for example in evidence.get("examples", []):
        occurrence_node = graph.add_node(
            "occurrence",
            {
                "context_protein_id": example.get("context_protein_id"),
                "neighbor_protein_id": example.get("neighbor_protein_id"),
                "relative_index": example.get("relative_index"),
                "neighbor_clusters": example.get("neighbor_clusters", {}),
            },
            created_by="deterministic_evidence_packet",
        )
        graph.add_edge(occurrence_node, candidate_node, "derived_from", created_by="deterministic_evidence_packet")
        neighbor = example.get("neighbor_protein") or {}
        if neighbor:
            annotation_node = graph.add_node(
                "annotation",
                {
                    "protein_id": example.get("neighbor_protein_id") or neighbor.get("protein_id"),
                    "product": neighbor.get("product"),
                    "gene_name": neighbor.get("gene_name"),
                    "pfam": neighbor.get("pfam"),
                    "interpro": neighbor.get("interpro"),
                    "kegg": neighbor.get("kegg"),
                    "cog_category": neighbor.get("cog_category"),
                    "cog_id": neighbor.get("cog_id"),
                },
                created_by="deterministic_evidence_packet",
            )
            graph.add_edge(annotation_node, occurrence_node, "observed_by", created_by="deterministic_evidence_packet")
    return graph.to_dict()


def _counts_by_type(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        node_type = str(node.get("type") or "")
        node_id = str(node.get("id") or "")
        if ":" not in node_id:
            continue
        _, index = node_id.rsplit(":", 1)
        if not index.isdigit():
            continue
        counts[node_type] = max(counts.get(node_type, 0), int(index))
    return counts
