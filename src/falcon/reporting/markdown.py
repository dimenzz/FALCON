from __future__ import annotations

from typing import Any


def render_agent_report(result: dict[str, Any]) -> str:
    candidate = result["candidate"]
    reasoning = result["reasoning"]
    sequence = result["sequence_evidence"]
    seed_summary = result.get("seed_summary") or {}
    ledger = result.get("ledger") or {}
    notebook = ledger.get("notebook") or {}
    agendas = ledger.get("agendas") or []
    audited_claims = ledger.get("audited_claims") or []
    tool_runs = ledger.get("tool_runs") or []

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
        "## Supported Claim",
        "",
    ]

    supported_claim = reasoning.get("supported_claim") or {}
    if supported_claim:
        lines.append(f"- Label: {supported_claim.get('label', '')}")
        if supported_claim.get("evidence_refs"):
            lines.append(f"- Evidence refs: {', '.join(supported_claim.get('evidence_refs', []))}")
    else:
        lines.append("- No supported claim recorded.")
    lines.append("")

    lines.extend(["## Seed Summary", ""])
    query_prior = seed_summary.get("query_prior") or {}
    target_consensus = seed_summary.get("target_consensus_annotation") or {}
    lines.append(f"- Query prior: {query_prior.get('function_description') or query_prior.get('header_description') or 'n/a'}")
    lines.append(f"- Target consensus product: {target_consensus.get('product') or 'n/a'}")
    lines.append(f"- Target consensus gene name: {target_consensus.get('gene_name') or 'n/a'}")
    lines.append("")

    lines.extend(["## Research Notebook", ""])
    lines.append(f"- Active question: {notebook.get('active_question') or 'n/a'}")
    if notebook.get("failed_bridges"):
        for bridge in notebook["failed_bridges"]:
            lines.append(f"- Failed bridge: {bridge.get('program_type')} - {bridge.get('reason')}")
    if notebook.get("escalation_signals"):
        for signal in notebook["escalation_signals"]:
            lines.append(f"- Escalation signal: {signal}")
    if notebook.get("recent_outcomes"):
        for outcome in notebook["recent_outcomes"][-5:]:
            lines.append(
                f"- Outcome: {outcome.get('step_id')} / {outcome.get('program_type')} -> {outcome.get('status')}"
            )
    if not notebook.get("failed_bridges") and not notebook.get("recent_outcomes"):
        lines.append("- No notebook updates recorded.")
    lines.append("")

    lines.extend(["## Research Agenda", ""])
    if agendas:
        latest = agendas[-1]
        lines.append(f"- Main question: {latest.get('main_question')}")
        lines.append(f"- Current program: {latest.get('current_program')}")
        for step in latest.get("steps", []):
            lines.append(f"- Step {step.get('step_id')}: {step.get('program_type')} - {step.get('goal')}")
    else:
        lines.append("- No agenda recorded.")
    lines.append("")

    lines.extend(["## Audited Evidence", ""])
    lines.append(f"- Examples inspected: {len(result['examples'])}")
    lines.append(f"- Protein sequence available: {sequence['protein']['available']}")
    lines.append(f"- DNA sequence available: {sequence['dna']['available']}")
    for claim in audited_claims:
        lines.append(
            f"- {claim.get('step_id')} / {claim.get('program_type')}: {claim.get('verdict')} ({claim.get('status')})"
        )
    if not audited_claims:
        lines.append("- No audited claims recorded.")
    lines.append("")

    lines.extend(["## Tool Runs", ""])
    for tool_run in tool_runs:
        lines.append(f"- {tool_run.get('tool')}: {tool_run.get('status')}")
    if not tool_runs:
        lines.append("- No tool runs recorded.")
    lines.append("")

    if reasoning.get("notebook_summary"):
        lines.extend(["## Notebook Summary", ""])
        for item in reasoning["notebook_summary"]:
            lines.append(f"- {item}")
        lines.append("")

    if reasoning.get("agenda_summary"):
        lines.extend(["## Agenda Summary", ""])
        for item in reasoning["agenda_summary"]:
            lines.append(f"- {item}")
        lines.append("")

    if reasoning.get("next_program_recommendations"):
        lines.extend(["## Next Program Recommendation", ""])
        for item in reasoning["next_program_recommendations"]:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(["## Deterministic Checks", ""])
    for item in result["falsification_checklist"]:
        lines.append(f"- [{item['status']}] {item['question']} - {item['evidence']}")

    lines.extend(["", "## Uncertainty", ""])
    if result["uncertainties"]:
        for uncertainty in result["uncertainties"]:
            lines.append(f"- {uncertainty}")
    else:
        lines.append("- No blocking uncertainty recorded.")
    lines.append("")
    return "\n".join(lines)
