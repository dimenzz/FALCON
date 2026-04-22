from __future__ import annotations

from copy import deepcopy
from typing import Any

from falcon.agent.team.graph import EvidenceGraph


def initialize_audit_ledger(
    *,
    candidate: dict[str, Any],
    seed_summary: dict[str, Any],
    occurrence_examples: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = EvidenceGraph()
    candidate_node = graph.add_node("candidate", dict(candidate), created_by="reasoning_runtime")
    seed_node = graph.add_node("seed_summary", dict(seed_summary), created_by="reasoning_runtime")
    graph.add_edge(seed_node, candidate_node, "refers_to", created_by="reasoning_runtime")
    for example in occurrence_examples:
        occurrence_node = graph.add_node(
            "occurrence",
            {
                "context_protein_id": example.get("context_protein_id"),
                "neighbor_protein_id": example.get("neighbor_protein_id"),
            },
            created_by="reasoning_runtime",
        )
        graph.add_edge(occurrence_node, candidate_node, "derived_from", created_by="reasoning_runtime")
    return {
        "candidate": deepcopy(candidate),
        "seed_summary": deepcopy(seed_summary),
        "occurrence_examples": deepcopy(occurrence_examples),
        "executed_steps": [],
        "tool_runs": [],
        "audited_claims": [],
        "contradictions": [],
        "final_supported_claim": {},
        "evidence_graph": graph.to_dict(),
    }


def record_tool_run(ledger: dict[str, Any], tool_run: dict[str, Any]) -> dict[str, Any]:
    run_index = len(ledger.setdefault("tool_runs", [])) + 1
    stored = deepcopy(tool_run)
    tool_name = str(stored.get("tool") or "tool")
    stored.setdefault("evidence_ref", f"TOOL:{tool_name}:{run_index}")
    ledger["tool_runs"].append(stored)

    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    candidate_node = _first_node_id(graph, "candidate")
    raw_node = graph.add_node(
        "raw_observation",
        {
            "tool": tool_name,
            "status": stored.get("status"),
            "evidence_ref": stored.get("evidence_ref"),
            "payload": deepcopy(stored),
        },
        created_by="audit_ledger",
    )
    summary_payload = {
        "tool": tool_name,
        "status": stored.get("status"),
        "evidence_ref": stored.get("evidence_ref"),
        "lifecycle": "active",
        "summary": deepcopy(stored.get("summary") or {}),
    }
    summary_node = graph.add_node("normalized_summary", summary_payload, created_by="audit_ledger")
    graph.add_edge(summary_node, raw_node, "derived_from", created_by="audit_ledger")
    if candidate_node is not None:
        graph.add_edge(raw_node, candidate_node, "refers_to", created_by="audit_ledger")
        graph.add_edge(summary_node, candidate_node, "refers_to", created_by="audit_ledger")
    ledger["evidence_graph"] = graph.to_dict()
    return stored


def record_audited_claim(ledger: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    stored = deepcopy(claim)
    ledger.setdefault("audited_claims", []).append(stored)

    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    candidate_node = _first_node_id(graph, "candidate")
    claim_node = graph.add_node("audited_claim", stored, created_by="audit_ledger")
    if candidate_node is not None:
        graph.add_edge(claim_node, candidate_node, "refers_to", created_by="audit_ledger")
    for evidence_ref in stored.get("evidence_refs") or []:
        summary_node = _find_summary_node_by_ref(graph, str(evidence_ref))
        if summary_node is not None:
            graph.add_edge(summary_node, claim_node, "supports", created_by="audit_ledger")
    ledger["evidence_graph"] = graph.to_dict()
    return stored


def _first_node_id(graph: EvidenceGraph, node_type: str) -> str | None:
    for node in graph.nodes:
        if node.get("type") == node_type:
            return str(node.get("id"))
    return None


def _find_summary_node_by_ref(graph: EvidenceGraph, evidence_ref: str) -> str | None:
    for node in graph.nodes:
        if node.get("type") != "normalized_summary":
            continue
        payload = node.get("payload") or {}
        if str(payload.get("evidence_ref") or "") == evidence_ref:
            return str(node.get("id"))
    return None
