from __future__ import annotations

from copy import deepcopy
from typing import Any

from falcon.agent.team.ledger import CandidateLedger
from falcon.tools.manifest import ToolManifest


def build_role_context_pack(
    *,
    role: str,
    ledger: CandidateLedger,
    evidence: dict[str, Any],
    tool_manifest: ToolManifest | None = None,
) -> dict[str, Any]:
    return {
        "role": role,
        "candidate_context": _candidate_context(ledger=ledger, evidence=evidence),
        "literature_context": _literature_context(ledger),
        "evidence_graph": _graph_slice(role=role, ledger=ledger),
        "open_questions": {
            "evidence_needs": deepcopy(ledger.get("evidence_needs", [])),
            "contradictions": deepcopy(ledger.get("contradiction_ledger", [])),
            "uncertainties": deepcopy(ledger.get("uncertainties", [])),
        },
        "tool_manifest": tool_manifest.to_prompt_payload() if tool_manifest is not None else [],
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
    if role in {"tool_planner", "evidence_auditor", "hypothesis_reviser", "synthesizer"}:
        return graph
    return {
        "nodes": [
            node
            for node in graph.get("nodes", [])
            if node.get("type") in {"candidate", "occurrence", "annotation", "literature_record", "hypothesis"}
        ],
        "edges": deepcopy(graph.get("edges", [])),
    }
