from __future__ import annotations

from copy import deepcopy
from typing import Any

from falcon.tools.manifest import ToolManifest


def build_context_workbench(
    *,
    role: str,
    ledger: dict[str, Any],
    evidence: dict[str, Any],
    candidate_context: dict[str, Any],
    tool_manifest: ToolManifest | None,
    dynamic_tools_enabled: bool = False,
) -> dict[str, Any]:
    sequence_evidence = ledger.get("sequence_evidence") or evidence.get("sequence_evidence") or {}
    return {
        "role": role,
        "tool_catalog": tool_manifest.to_prompt_payload() if tool_manifest is not None else [],
        "data_contracts": _data_contracts(),
        "artifact_index": _artifact_index(sequence_evidence=sequence_evidence, ledger=ledger),
        "context_views": _context_views(
            candidate_context=candidate_context,
            examples=evidence.get("examples") or ledger.get("examples") or [],
            ledger=ledger,
            role=role,
        ),
        "dynamic_tool_contract": _dynamic_tool_contract(enabled=dynamic_tools_enabled),
    }


def _data_contracts() -> dict[str, Any]:
    return {
        "cluster_vs_occurrence": (
            "Cluster-level statistics prioritize candidates; occurrence-level examples are the canonical evidence "
            "for genomic context, annotations, and sequence access."
        ),
        "occurrence_context": {
            "path": "examples[].context.context[]",
            "fields": {
                "relative_index": "gene offset from the seed/context protein; 0 is the seed/context protein",
                "protein": "protein annotation record from proteins.db",
                "clusters": "cluster representatives keyed by clustering level such as 90 and 30",
                "is_target": "whether this context entry is the seed/context protein",
            },
        },
        "candidate_neighbor": {
            "path": "examples[].neighbor_protein",
            "warning": "The candidate neighbor protein is not the seed/query protein.",
        },
        "sequence_evidence": {
            "protein_path": "sequence_evidence.protein",
            "dna_path": "sequence_evidence.dna",
            "sequence_field": "sequence is present only when sequences were included or required by team workflow",
        },
        "tool_outputs": {
            "path": "tool_observations[]",
            "requirement": "Tool conclusions must be judged against each tool output_contract and limitations.",
        },
        "tool_summaries": {
            "path": "tool_summaries[]",
            "requirement": "Planner consumes summaries first; auditor can trace each summary back to raw observations.",
        },
    }


def _artifact_index(*, sequence_evidence: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    protein = sequence_evidence.get("protein") or {}
    dna = sequence_evidence.get("dna") or {}
    return {
        "ledger": {"kind": "inline_json", "path": "candidate_ledger"},
        "occurrence_context": {"kind": "inline_json", "path": "examples[].context.context[]"},
        "candidate_protein_sequence": {
            "kind": "inline_json",
            "path": "sequence_evidence.protein.sequence",
            "available": bool(protein.get("sequence")),
            "protein_id": protein.get("protein_id"),
            "fasta_path": protein.get("fasta_path"),
        },
        "candidate_dna_sequence": {
            "kind": "inline_json",
            "path": "sequence_evidence.dna.sequence",
            "available": bool(dna.get("sequence")),
            "protein_id": dna.get("protein_id"),
            "fasta_path": dna.get("fasta_path"),
        },
        "tool_outputs": {
            "kind": "inline_json",
            "path": "tool_observations[]",
            "count": len(ledger.get("tool_observations", [])),
        },
        "tool_summaries": {
            "kind": "inline_json",
            "path": "tool_summaries[]",
            "count": len(ledger.get("tool_summaries", [])),
        },
    }


def _context_views(*, candidate_context: dict[str, Any], examples: list[dict[str, Any]], ledger: dict[str, Any], role: str) -> dict[str, Any]:
    tool_summaries = deepcopy(ledger.get("tool_summaries", []))
    audit_findings = deepcopy((ledger.get("audit") or {}).get("findings", []))
    return {
        "candidate_identity": deepcopy(candidate_context.get("representative_neighbor", {})),
        "family_naming": deepcopy(ledger.get("family_naming", {})),
        "literature_scopes": deepcopy((ledger.get("literature") or {}).get("scoped_summaries", [])),
        "sequence_availability": {
            "protein": bool((candidate_context.get("sequence") or {}).get("sequence")),
            "length": (candidate_context.get("sequence") or {}).get("length"),
        },
        "full_context_summary": [_summarize_context_example(example) for example in examples],
        "tool_summaries": _role_visible_tool_summaries(role=role, tool_summaries=tool_summaries, audit_findings=audit_findings),
    }


def _summarize_context_example(example: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for item in (example.get("context") or {}).get("context", []):
        protein = item.get("protein") or {}
        entries.append(
            {
                "relative_index": item.get("relative_index"),
                "protein_id": protein.get("protein_id"),
                "product": protein.get("product"),
                "gene_name": protein.get("gene_name"),
                "pfam": protein.get("pfam"),
                "interpro": protein.get("interpro"),
                "clusters": deepcopy(item.get("clusters", {})),
            }
        )
    return {
        "context_protein_id": example.get("context_protein_id"),
        "neighbor_protein_id": example.get("neighbor_protein_id"),
        "entries": entries,
    }


def _dynamic_tool_contract(*, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "script_contract": "define run(input_payload: dict) -> dict",
        "execution": "FALCON runs the script with an outer Python subprocess and captures stdout/stderr logs.",
        "allowed_inputs": [
            "candidate ledger JSON",
            "occurrence context JSON",
            "candidate protein or DNA sequence in the provided artifact index",
            "prior tool result JSON",
        ],
        "required_output": ["status", "answer", "observations", "evidence_refs", "limitations"],
        "forbidden": ["network access", "nested subprocess calls", "writes outside the managed output JSON"],
    }


def _role_visible_tool_summaries(*, role: str, tool_summaries: list[dict[str, Any]], audit_findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if role == "synthesizer":
        cited_refs = {
            ref
            for finding in audit_findings
            for ref in (finding.get("evidence_refs") or [])
            if isinstance(ref, str)
        }
        return [summary for summary in tool_summaries if str(summary.get("raw_observation_ref") or "") in cited_refs]
    return tool_summaries
