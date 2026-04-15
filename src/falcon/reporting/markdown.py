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
    ]
    if reasoning.get("evidence"):
        lines.extend(["## Reasoning Evidence", ""])
        for evidence in reasoning["evidence"]:
            lines.append(f"- {evidence}")
        lines.append("")

    ledger = result.get("ledger")
    if ledger:
        literature = ledger.get("literature", {})
        brief = literature.get("brief", {})
        lines.extend(["## Literature Grounding", ""])
        if brief:
            lines.append(f"- Summary: {brief.get('summary', '')}")
            for finding in brief.get("key_findings", []):
                lines.append(f"- Finding: {finding}")
            for constraint in brief.get("constraints", []):
                lines.append(f"- Constraint: {constraint}")
        else:
            lines.append("- No literature brief recorded.")
        for record in literature.get("records", [])[:5]:
            ref = record.get("evidence_ref")
            title = record.get("title")
            pmid = record.get("pmid")
            lines.append(f"- {ref}: {title} (PMID: {pmid})")
        lines.append("")

        graph = ledger.get("evidence_graph") or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        lines.extend(["## Evidence Graph", ""])
        lines.append(f"- Nodes: {len(nodes)}")
        lines.append(f"- Edges: {len(edges)}")
        node_type_counts: dict[str, int] = {}
        for node in nodes:
            node_type = str(node.get("type") or "unknown")
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
        for node_type, count in sorted(node_type_counts.items()):
            lines.append(f"- {node_type}: {count}")
        if not nodes:
            lines.append("- No evidence graph nodes recorded.")
        lines.append("")

        lines.extend(["## Hypotheses", ""])
        for hypothesis in ledger.get("hypotheses", []):
            lines.append(f"- {hypothesis.get('id')}: {hypothesis.get('claim')}")
        if not ledger.get("hypotheses"):
            lines.append("- No hypotheses recorded.")
        lines.append("")

        lines.extend(["## Hypothesis-Specific Falsification Tests", ""])
        for test in ledger.get("falsification_tests", []):
            lines.append(f"- {test.get('id')} ({test.get('hypothesis_id')}): {test.get('question')}")
            lines.append(f"  Support: {test.get('support_criteria')}")
            lines.append(f"  Weaken: {test.get('weaken_criteria')}")
            lines.append(f"  Falsify: {test.get('falsify_criteria')}")
        if not ledger.get("falsification_tests"):
            lines.append("- No hypothesis-specific tests recorded.")
        lines.append("")

        lines.extend(["## Audit and Revision", ""])
        for finding in ledger.get("audit", {}).get("findings", []):
            lines.append(
                f"- {finding.get('test_id')} / {finding.get('hypothesis_id')}: "
                f"{finding.get('verdict')} - {finding.get('rationale')}"
            )
        for revision in ledger.get("revisions", []):
            for hypothesis in revision.get("revised_hypotheses", []):
                lines.append(
                    f"- Revised {hypothesis.get('id')} v{hypothesis.get('version')}: "
                    f"{hypothesis.get('status')} - {hypothesis.get('claim')}"
                )
        if not ledger.get("audit", {}).get("findings") and not ledger.get("revisions"):
            lines.append("- No audit findings recorded.")
        lines.append("")

        lines.extend(["## Contradiction Ledger", ""])
        if ledger.get("contradiction_ledger"):
            for contradiction in ledger["contradiction_ledger"]:
                lines.append(f"- {contradiction}")
        else:
            lines.append("- No contradictions recorded.")
        lines.append("")

    if "llm_trace" in result:
        trace = result["llm_trace"]
        lines.extend(
            [
                "## LLM Agent Loop",
                "",
                f"- Mode: {trace['mode']}",
                f"- Provider: {trace['provider']}",
                f"- Iterations: {trace['iterations']}",
                f"- Finalized: {trace['finalized']}",
            ]
        )
        for hypothesis in trace.get("hypotheses", []):
            lines.append(f"- Hypothesis: {hypothesis}")
        for contradiction in trace.get("contradictions", []):
            lines.append(f"- Contradiction: {contradiction}")
        lines.append("")

    if "team_trace" in result:
        trace = result["team_trace"]
        lines.extend(
            [
                "## Multi-Agent Review",
                "",
                f"- Rounds: {trace['rounds']}",
                f"- Ledger blocked: {trace.get('ledger_blocked', bool(trace.get('blocked_step')))}",
            ]
        )
        for hypothesis in trace.get("hypotheses", []):
            if isinstance(hypothesis, dict):
                lines.append(f"- Hypothesis: {hypothesis.get('claim')}")
            else:
                lines.append(f"- Hypothesis: {hypothesis}")
        for contradiction in trace.get("contradictions", trace.get("criticisms", [])):
            lines.append(f"- Contradiction: {contradiction}")
        lines.append("")

    if result.get("tool_results"):
        lines.extend(["## Tool Results", ""])
        for tool_result in result["tool_results"]:
            lines.append(f"- {tool_result.get('tool')}: {tool_result.get('status')}")
        lines.append("")

    checklist_title = "## Deterministic Checks" if ledger else "## Falsification Checklist"
    lines.extend([checklist_title, ""])
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
