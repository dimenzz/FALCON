from __future__ import annotations

from copy import deepcopy
from typing import Any

from falcon.agent.team.graph import EvidenceGraph, initialize_evidence_graph


CandidateLedger = dict[str, Any]


def initialize_ledger(
    *,
    candidate_index: int,
    candidate_slug: str,
    evidence: dict[str, Any],
) -> CandidateLedger:
    return {
        "candidate_index": candidate_index,
        "candidate_slug": candidate_slug,
        "candidate": deepcopy(evidence.get("candidate", {})),
        "examples": deepcopy(evidence.get("examples", [])),
        "sequence_evidence": deepcopy(evidence.get("sequence_evidence", {})),
        "deterministic_checks": deepcopy(
            evidence.get("deterministic_checks") or evidence.get("falsification_checklist") or []
        ),
        "literature": {
            "queries": [],
            "records": [],
            "brief": {},
            "failed_queries": [],
        },
        "hypotheses": [],
        "falsification_tests": [],
        "evidence_needs": [],
        "tool_plan": [],
        "tool_observations": [],
        "audit": {"findings": []},
        "revisions": [],
        "contradiction_ledger": [],
        "final": {},
        "uncertainties": deepcopy(evidence.get("uncertainties", [])),
        "evidence_graph": initialize_evidence_graph(candidate=deepcopy(evidence.get("candidate", {})), evidence=evidence),
    }


def add_literature_records(ledger: CandidateLedger, records: list[dict[str, Any]]) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for record in records:
        payload = dict(record)
        if "evidence_ref" not in payload:
            payload["evidence_ref"] = f"L{len(ledger['literature']['records']) + 1}"
        ledger["literature"]["records"].append(payload)
        node_id = graph.add_node("literature_record", payload, created_by="search_literature")
        _link_to_candidate(graph, node_id, created_by="search_literature")
    ledger["evidence_graph"] = graph.to_dict()


def add_tool_observations(ledger: CandidateLedger, observations: list[dict[str, Any]]) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for observation in observations:
        payload = dict(observation)
        if "evidence_ref" not in payload:
            payload["evidence_ref"] = f"TOOL:{payload.get('tool', 'unknown')}:{len(ledger['tool_observations']) + 1}"
        ledger["tool_observations"].append(payload)
        node_id = graph.add_node("tool_observation", payload, created_by="tool_scheduler")
        _link_to_candidate(graph, node_id, created_by="tool_scheduler")
    ledger["evidence_graph"] = graph.to_dict()


def mark_blocked(
    ledger: CandidateLedger,
    *,
    role: str,
    attempts: int,
    error: str,
) -> None:
    ledger["blocked_step"] = {
        "role": role,
        "attempts": attempts,
        "error": error,
    }


def add_hypothesis_nodes(ledger: CandidateLedger, hypotheses: list[dict[str, Any]], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for hypothesis in hypotheses:
        node_id = graph.add_node("hypothesis", hypothesis, created_by=created_by)
        _link_to_candidate(graph, node_id, created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_falsification_test_nodes(ledger: CandidateLedger, tests: list[dict[str, Any]], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for test in tests:
        node_id = graph.add_node("falsification_test", test, created_by=created_by)
        _link_to_hypothesis(graph, node_id, str(test.get("hypothesis_id") or ""), "tests", created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_evidence_need_nodes(ledger: CandidateLedger, needs: list[dict[str, Any]], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for need in needs:
        node_id = graph.add_node("evidence_need", need, created_by=created_by)
        _link_to_test(graph, node_id, str(need.get("test_id") or ""), "derived_from", created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_tool_request_nodes(ledger: CandidateLedger, requests: list[dict[str, Any]], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for request in requests:
        node_id = graph.add_node("tool_request", request, created_by=created_by)
        _link_to_candidate(graph, node_id, created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_audit_nodes(ledger: CandidateLedger, findings: list[dict[str, Any]], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    for finding in findings:
        node_id = graph.add_node("audit_finding", finding, created_by=created_by)
        verdict = str(finding.get("verdict") or "unresolved")
        if verdict in {"support", "weaken", "falsify", "contradict"}:
            edge_type = {"support": "supports", "weaken": "weakens", "falsify": "falsifies", "contradict": "contradicts"}[verdict]
        else:
            edge_type = "observed_by"
        _link_to_hypothesis(graph, node_id, str(finding.get("hypothesis_id") or ""), edge_type, created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_revision_node(ledger: CandidateLedger, revision: dict[str, Any], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    node_id = graph.add_node("revision", revision, created_by=created_by)
    _link_to_candidate(graph, node_id, created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def add_final_claim_node(ledger: CandidateLedger, final: dict[str, Any], *, created_by: str) -> None:
    graph = EvidenceGraph.from_dict(ledger.get("evidence_graph"))
    node_id = graph.add_node("final_claim", final, created_by=created_by)
    _link_to_candidate(graph, node_id, created_by=created_by)
    ledger["evidence_graph"] = graph.to_dict()


def _link_to_candidate(graph: EvidenceGraph, source: str, *, created_by: str) -> None:
    candidate_id = _first_node_id(graph, "candidate")
    if candidate_id:
        graph.add_edge(source, candidate_id, "derived_from", created_by=created_by)


def _link_to_hypothesis(graph: EvidenceGraph, source: str, hypothesis_id: str, edge_type: str, *, created_by: str) -> None:
    target = _node_id_by_payload_id(graph, "hypothesis", hypothesis_id)
    if target:
        graph.add_edge(source, target, edge_type, created_by=created_by)


def _link_to_test(graph: EvidenceGraph, source: str, test_id: str, edge_type: str, *, created_by: str) -> None:
    target = _node_id_by_payload_id(graph, "falsification_test", test_id)
    if target:
        graph.add_edge(source, target, edge_type, created_by=created_by)


def _first_node_id(graph: EvidenceGraph, node_type: str) -> str | None:
    for node in graph.nodes:
        if node.get("type") == node_type:
            return str(node.get("id"))
    return None


def _node_id_by_payload_id(graph: EvidenceGraph, node_type: str, payload_id: str) -> str | None:
    for node in graph.nodes:
        if node.get("type") != node_type:
            continue
        payload = node.get("payload") or {}
        if str(payload.get("id") or "") == payload_id:
            return str(node.get("id"))
    return None
