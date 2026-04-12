from __future__ import annotations

from typing import Any


def render_agent_report(result: dict[str, Any]) -> str:
    candidate = result["candidate"]
    reasoning = result["reasoning"]
    sequence = result["sequence_evidence"]
    lines = [
        f"# Candidate {candidate['query_id']} / {candidate['cluster_30']}",
        "",
        "## Summary",
        "",
        f"- Status: {reasoning['status']}",
        f"- Rationale: {reasoning['rationale']}",
        f"- Presence: {candidate.get('presence_contexts')} of {candidate.get('query_contexts')} contexts",
        f"- Fold enrichment: {candidate.get('fold_enrichment')}",
        f"- q-value: {candidate.get('q_value')}",
        "",
        "## Evidence",
        "",
        f"- Examples inspected: {len(result['examples'])}",
        f"- Protein sequence available: {sequence['protein']['available']}",
        f"- DNA sequence available: {sequence['dna']['available']}",
        "",
        "## Falsification Checklist",
        "",
    ]
    for item in result["falsification_checklist"]:
        lines.append(f"- [{item['status']}] {item['question']} - {item['evidence']}")

    lines.extend(["", "## Uncertainty", ""])
    if result["uncertainties"]:
        for uncertainty in result["uncertainties"]:
            lines.append(f"- {uncertainty}")
    else:
        lines.append("- No blocking uncertainty recorded in this deterministic MVP.")
    lines.append("")
    return "\n".join(lines)
