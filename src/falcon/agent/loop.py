from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

from falcon.agent.actions import AgentAction, AgentActionError, parse_agent_action
from falcon.agent.prompts import PromptPack
from falcon.agent.providers import LLMProvider


@dataclass(frozen=True)
class AgentLoopResult:
    reasoning: dict[str, Any]
    trace_summary: dict[str, Any]
    trace_records: list[dict[str, Any]]
    call_records: list[dict[str, Any]]
    uncertainties: list[str]


def run_llm_loop(
    *,
    candidate_index: int,
    candidate_slug: str,
    evidence: dict[str, Any],
    provider: LLMProvider,
    prompt_pack: PromptPack,
    max_iterations: int,
    mode: str,
) -> AgentLoopResult:
    hypotheses: list[str] = []
    contradictions: list[str] = []
    trace_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    uncertainties: list[str] = []
    messages = _initial_messages(prompt_pack, evidence)

    for iteration in range(1, int(max_iterations) + 1):
        response = provider.complete(
            messages,
            metadata={
                "candidate_index": candidate_index,
                "candidate_slug": candidate_slug,
                "iteration": iteration,
                "mode": mode,
            },
        )
        call_records.append(
            {
                "candidate_index": candidate_index,
                "candidate_slug": candidate_slug,
                "iteration": iteration,
                "provider": response.provider,
                "messages": [dict(message) for message in messages],
                "response_content": response.content,
                "raw_response": response.raw,
            }
        )

        try:
            action = parse_agent_action(response.content, allowed_actions=prompt_pack.allowed_actions)
            observation = _execute_read_only_action(
                action=action,
                evidence=evidence,
                hypotheses=hypotheses,
                contradictions=contradictions,
            )
            action_payload: dict[str, Any] = action.payload
        except AgentActionError as exc:
            action_payload = {"action": "invalid", "raw_response": response.content}
            observation = {
                "error": str(exc),
                "allowed_actions": list(prompt_pack.allowed_actions),
            }
            uncertainties.append(str(exc))

        trace_records.append(
            {
                "candidate_index": candidate_index,
                "candidate_slug": candidate_slug,
                "iteration": iteration,
                "action": action_payload,
                "observation": observation,
            }
        )
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": "Observation:\n" + json.dumps(observation, sort_keys=True)})

        if action_payload.get("action") == "finalize" and "error" not in observation:
            final_uncertainties = _string_list(action_payload.get("uncertainties"))
            uncertainties.extend(final_uncertainties)
            return AgentLoopResult(
                reasoning={
                    "status": action_payload["status"],
                    "rationale": action_payload["rationale"],
                    "evidence": _string_list(action_payload.get("evidence")),
                },
                trace_summary={
                    "mode": mode,
                    "provider": response.provider,
                    "prompt_pack": str(prompt_pack.path),
                    "iterations": iteration,
                    "finalized": True,
                    "hypotheses": hypotheses,
                    "contradictions": contradictions,
                },
                trace_records=trace_records,
                call_records=call_records,
                uncertainties=uncertainties,
            )

    return AgentLoopResult(
        reasoning={
            "status": "incomplete",
            "rationale": f"Reached maximum LLM iterations ({max_iterations}) before finalize action.",
            "evidence": [],
        },
        trace_summary={
            "mode": mode,
            "provider": getattr(provider, "name", "unknown"),
            "prompt_pack": str(prompt_pack.path),
            "iterations": int(max_iterations),
            "finalized": False,
            "hypotheses": hypotheses,
            "contradictions": contradictions,
        },
        trace_records=trace_records,
        call_records=call_records,
        uncertainties=uncertainties,
    )


def _initial_messages(prompt_pack: PromptPack, evidence: dict[str, Any]) -> list[dict[str, str]]:
    system = "\n\n".join(
        [
            prompt_pack.system,
            "Developer guidance:\n" + prompt_pack.developer_guidance,
            "Tool policy:\n" + prompt_pack.tool_policy,
            "Output contract:\n" + prompt_pack.output_contract,
            "Allowed actions:\n" + ", ".join(prompt_pack.allowed_actions),
        ]
    )
    user = (
        "Evaluate this candidate with a falsification-first loop. "
        "Return one JSON action at a time.\n\nEvidence:\n"
        + json.dumps(_compact_evidence(evidence), sort_keys=True)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate": evidence["candidate"],
        "falsification_checklist": evidence["falsification_checklist"],
        "example_count": len(evidence["examples"]),
        "example_annotations": _annotation_rows(evidence["examples"]),
        "sequence_evidence": {
            "protein": _without_sequence(evidence["sequence_evidence"]["protein"]),
            "dna": _without_sequence(evidence["sequence_evidence"]["dna"]),
        },
        "uncertainties": evidence.get("uncertainties", []),
    }


def _execute_read_only_action(
    *,
    action: AgentAction,
    evidence: dict[str, Any],
    hypotheses: list[str],
    contradictions: list[str],
) -> dict[str, Any]:
    if action.name == "propose_hypothesis":
        hypothesis = action.payload.get("hypothesis")
        if isinstance(hypothesis, str) and hypothesis:
            hypotheses.append(hypothesis)
        return {"recorded_hypotheses": hypotheses}

    if action.name == "request_context_summary":
        return {"examples": _context_rows(evidence["examples"])}

    if action.name == "request_sequence_summary":
        return {
            "protein": _without_sequence(evidence["sequence_evidence"]["protein"]),
            "dna": _without_sequence(evidence["sequence_evidence"]["dna"]),
        }

    if action.name == "compare_example_annotations":
        return {"annotations": _annotation_rows(evidence["examples"])}

    if action.name == "record_contradiction":
        contradiction = action.payload.get("contradiction") or action.payload.get("reason")
        if isinstance(contradiction, str) and contradiction:
            contradictions.append(contradiction)
        return {"recorded_contradictions": contradictions}

    if action.name == "finalize":
        return {"finalized": True, "status": action.payload["status"]}

    raise AgentActionError(f"Unhandled action: {action.name}")


def _context_rows(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for example in examples:
        context = example.get("context") or {}
        rows.append(
            {
                "context_protein_id": example.get("context_protein_id"),
                "neighbor_protein_id": example.get("neighbor_protein_id"),
                "relative_index": example.get("relative_index"),
                "neighbor_product": (example.get("neighbor_protein") or {}).get("product"),
                "neighbor_clusters": example.get("neighbor_clusters", {}),
                "context_products": [
                    {
                        "protein_id": (item.get("protein") or {}).get("protein_id"),
                        "product": (item.get("protein") or {}).get("product"),
                        "relative_index": item.get("relative_index"),
                        "is_target": item.get("is_target"),
                        "clusters": item.get("clusters", {}),
                    }
                    for item in context.get("context", [])
                ],
            }
        )
    return rows


def _annotation_rows(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for example in examples:
        neighbor = example.get("neighbor_protein") or {}
        context = example.get("context") or {}
        target = context.get("target") or {}
        rows.append(
            {
                "context_protein_id": example.get("context_protein_id"),
                "neighbor_protein_id": example.get("neighbor_protein_id"),
                "neighbor_product": neighbor.get("product"),
                "neighbor_gene_name": neighbor.get("gene_name"),
                "neighbor_pfam": neighbor.get("pfam"),
                "neighbor_interpro": neighbor.get("interpro"),
                "target_product": target.get("product"),
                "relative_index": example.get("relative_index"),
            }
        )
    return rows


def _without_sequence(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "sequence"}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
