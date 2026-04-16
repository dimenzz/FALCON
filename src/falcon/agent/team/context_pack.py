from __future__ import annotations

from copy import deepcopy
from typing import Any

from falcon.agent.team.ledger import CandidateLedger
from falcon.agent.team.workbench import build_context_workbench
from falcon.tools.manifest import ToolManifest


def build_role_context_pack(
    *,
    role: str,
    ledger: CandidateLedger,
    evidence: dict[str, Any],
    tool_manifest: ToolManifest | None = None,
    dynamic_tools_enabled: bool = False,
) -> dict[str, Any]:
    candidate_context = _candidate_context(ledger=ledger, evidence=evidence)
    return {
        "role": role,
        "candidate_context": candidate_context,
        "family_naming": deepcopy(ledger.get("family_naming", {})),
        "literature_context": _literature_context(ledger),
        "evidence_graph": _graph_slice(role=role, ledger=ledger),
        "open_questions": {
            "evidence_needs": deepcopy(ledger.get("evidence_needs", [])),
            "contradictions": deepcopy(ledger.get("contradiction_ledger", [])),
            "uncertainties": deepcopy(ledger.get("uncertainties", [])),
        },
        "tool_manifest": tool_manifest.to_prompt_payload() if tool_manifest is not None else [],
        "context_workbench": build_context_workbench(
            role=role,
            ledger=ledger,
            evidence=evidence,
            candidate_context=candidate_context,
            tool_manifest=tool_manifest,
            dynamic_tools_enabled=dynamic_tools_enabled,
        ),
    }


def _candidate_context(*, ledger: CandidateLedger, evidence: dict[str, Any]) -> dict[str, Any]:
    examples = evidence.get("examples") or ledger.get("examples") or []
    representative = _representative_neighbor(examples, ledger)
    return {
        "evidence_boundary": "candidate_neighbor_protein_is_not_the_seed_or_context_query_protein",
        "candidate": deepcopy(ledger.get("candidate", {})),
        "representative_neighbor": representative,
        "sequence": deepcopy((ledger.get("sequence_evidence") or evidence.get("sequence_evidence") or {}).get("protein", {})),
        "deterministic_checks": deepcopy(ledger.get("deterministic_checks", [])),
        "occurrence_examples": [_compact_example(example) for example in examples],
    }


def _representative_neighbor(examples: list[dict[str, Any]], ledger: CandidateLedger) -> dict[str, Any]:
    if examples:
        example = examples[0]
        neighbor = example.get("neighbor_protein") or {}
        return {
            "protein_id": example.get("neighbor_protein_id") or neighbor.get("protein_id"),
            "product": neighbor.get("product"),
            "gene_name": neighbor.get("gene_name"),
            "pfam": neighbor.get("pfam"),
            "interpro": neighbor.get("interpro"),
            "kegg": neighbor.get("kegg"),
            "cog_category": neighbor.get("cog_category"),
            "cog_id": neighbor.get("cog_id"),
            "clusters": deepcopy(example.get("neighbor_clusters", {})),
            "relative_index": example.get("relative_index"),
        }
    protein = (ledger.get("sequence_evidence") or {}).get("protein") or {}
    return {
        "protein_id": protein.get("protein_id"),
        "product": None,
        "gene_name": None,
        "pfam": None,
        "interpro": None,
        "kegg": None,
        "cog_category": None,
        "cog_id": None,
        "clusters": {},
        "relative_index": None,
    }


def _compact_example(example: dict[str, Any]) -> dict[str, Any]:
    neighbor = example.get("neighbor_protein") or {}
    return {
        "context_protein_id": example.get("context_protein_id"),
        "neighbor_protein_id": example.get("neighbor_protein_id") or neighbor.get("protein_id"),
        "relative_index": example.get("relative_index"),
        "neighbor_clusters": deepcopy(example.get("neighbor_clusters", {})),
        "neighbor_annotation": {
            "product": neighbor.get("product"),
            "gene_name": neighbor.get("gene_name"),
            "pfam": neighbor.get("pfam"),
            "interpro": neighbor.get("interpro"),
            "kegg": neighbor.get("kegg"),
            "cog_category": neighbor.get("cog_category"),
            "cog_id": neighbor.get("cog_id"),
        },
    }


def _literature_context(ledger: CandidateLedger) -> dict[str, Any]:
    literature = ledger.get("literature") or {}
    return {
        "queries": deepcopy(literature.get("queries", [])),
        "brief": deepcopy(literature.get("brief", {})),
        "scoped_summaries": deepcopy(literature.get("scoped_summaries", [])),
        "records": [_compact_literature_record(record) for record in literature.get("records", [])],
        "failed_queries": deepcopy(literature.get("failed_queries", [])),
    }


def _compact_literature_record(record: dict[str, Any]) -> dict[str, Any]:
    abstract = str(record.get("abstract") or "")
    return {
        "evidence_ref": record.get("evidence_ref"),
        "source": record.get("source"),
        "title": record.get("title"),
        "pmid": record.get("pmid"),
        "doi": record.get("doi"),
        "abstract_excerpt": abstract[:600],
    }


def _graph_slice(*, role: str, ledger: CandidateLedger) -> dict[str, Any]:
    graph = deepcopy(ledger.get("evidence_graph", {"nodes": [], "edges": []}))
    if role == "evidence_auditor":
        return graph
    if role == "tool_planner":
        return _filter_graph(
            graph,
            allowed_types={
                "candidate",
                "occurrence",
                "annotation",
                "family_term_selection",
                "literature_summary",
                "hypothesis",
                "falsification_test",
                "evidence_need",
                "tool_request",
                "tool_summary",
            },
        )
    if role == "hypothesis_reviser":
        return _filter_graph(
            graph,
            allowed_types={
                "candidate",
                "family_term_selection",
                "literature_summary",
                "hypothesis",
                "falsification_test",
                "evidence_need",
                "tool_summary",
                "audit_finding",
            },
        )
    if role == "synthesizer":
        return _filter_graph(
            graph,
            allowed_types={
                "candidate",
                "family_term_selection",
                "literature_summary",
                "hypothesis",
                "audit_finding",
                "revision",
                "final_claim",
            },
        )
    return {
        "nodes": [
            node
            for node in graph.get("nodes", [])
            if node.get("type")
            in {"candidate", "occurrence", "annotation", "literature_record", "literature_summary", "family_term_selection", "hypothesis"}
        ],
        "edges": deepcopy(graph.get("edges", [])),
    }


def _filter_graph(graph: dict[str, Any], *, allowed_types: set[str]) -> dict[str, Any]:
    nodes = [node for node in graph.get("nodes", []) if node.get("type") in allowed_types]
    allowed_ids = {str(node.get("id")) for node in nodes}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if str(edge.get("source")) in allowed_ids and str(edge.get("target")) in allowed_ids
    ]
    return {"nodes": nodes, "edges": edges}
