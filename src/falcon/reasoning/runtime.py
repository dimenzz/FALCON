from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

from falcon.agent.providers import LLMProvider
from falcon.agent.team.roles.base import RoleRunner
from falcon.evidence.ledger import initialize_audit_ledger, record_audited_claim, record_tool_run
from falcon.reasoning.cohort_investigator import (
    compare_candidate_lengths,
    compare_neighbor_covariation,
    summarize_cohort_patterns,
)
from falcon.reasoning.notebook import initialize_notebook
from falcon.reasoning.programs import ResearchAgenda, RuntimeSynthesis
from falcon.tools.accession_enrichment import AccessionEnricher
from falcon.tools.agent_registry import EvidenceToolExecutor
from falcon.tools.semantic_bridge import resolve_semantic_bridge


@dataclass(frozen=True)
class ResearchRuntimeResult:
    reasoning: dict[str, Any]
    ledger: dict[str, Any]
    role_calls: list[dict[str, Any]]


def run_research_runtime(
    *,
    candidate_index: int,
    candidate_slug: str,
    runtime_inputs: dict[str, Any],
    provider: LLMProvider,
    tool_executor: EvidenceToolExecutor,
    max_rounds: int,
    prompt_dir: Path | str | None = None,
    schema_retries: int = 2,
    accession_enricher: AccessionEnricher | None = None,
    accession_cache_dir: str | None = None,
    event_logger: Any | None = None,
) -> ResearchRuntimeResult:
    role_calls: list[dict[str, Any]] = []
    notebook = initialize_notebook(
        seed_summary=_seed_summary_model(runtime_inputs["seed_summary"]),
        active_question="What is the candidate system role?",
    )
    ledger = initialize_audit_ledger(
        candidate=runtime_inputs["candidate_summary"],
        seed_summary=runtime_inputs["seed_summary"],
        occurrence_examples=runtime_inputs["occurrence_bundle"].get("examples", []),
    )
    ledger["notebook"] = notebook
    ledger["agendas"] = []
    runner = RoleRunner(
        provider=provider,
        role_instructions=load_reasoning_role_instructions(prompt_dir),
        candidate_index=candidate_index,
        candidate_slug=candidate_slug,
        schema_retries=schema_retries,
        role_calls=role_calls,
        event_logger=event_logger,
    )

    for round_index in range(1, max(1, int(max_rounds)) + 1):
        planner_payload = {
            "candidate_summary": runtime_inputs["candidate_summary"],
            "seed_summary": runtime_inputs["seed_summary"],
            "candidate_neighbor_summary": runtime_inputs["candidate_neighbor_summary"],
            "occurrence_bundle_summary": {
                "example_count": len(runtime_inputs["occurrence_bundle"].get("examples", [])),
                "sequence_availability": runtime_inputs["occurrence_bundle"].get("sequence_evidence", {}),
                "candidate_cohort_size": len(runtime_inputs["occurrence_bundle"].get("candidate_cohort", [])),
            },
            "notebook": notebook,
            "previous_agendas": ledger["agendas"],
        }
        agenda = runner.call(
            trace_role="program_planner",
            prompt_role="program_planner",
            schema=ResearchAgenda,
            payload=planner_payload,
        )
        agenda_payload = agenda.model_dump(mode="json")
        agenda_payload["round"] = round_index
        ledger["agendas"].append(agenda_payload)
        step = agenda.steps[0]
        step_result = _execute_step(
            step=step.model_dump(mode="json"),
            runtime_inputs=runtime_inputs,
            tool_executor=tool_executor,
            accession_enricher=accession_enricher,
            accession_cache_dir=accession_cache_dir,
        )
        if step_result.get("tool_runs"):
            for run in step_result["tool_runs"]:
                record_tool_run(ledger, run)
        audited = _audit_step(step=step.model_dump(mode="json"), step_result=step_result)
        record_audited_claim(ledger, audited)
        _update_notebook(
            notebook=notebook,
            step=step.model_dump(mode="json"),
            step_result=step_result,
            audited_claim=audited,
        )
        ledger["notebook"] = notebook

    synthesis = runner.call(
        trace_role="synthesizer",
        prompt_role="synthesizer",
        schema=RuntimeSynthesis,
        payload={
            "candidate_summary": runtime_inputs["candidate_summary"],
            "seed_summary": runtime_inputs["seed_summary"],
            "candidate_neighbor_summary": runtime_inputs["candidate_neighbor_summary"],
            "notebook": notebook,
            "agendas": ledger["agendas"],
            "audited_claims": ledger["audited_claims"],
            "tool_runs": ledger["tool_runs"],
        },
    )
    reasoning = synthesis.model_dump(mode="json")
    ledger["final_supported_claim"] = dict(reasoning.get("supported_claim") or {})
    return ResearchRuntimeResult(reasoning=reasoning, ledger=ledger, role_calls=role_calls)


def load_reasoning_role_instructions(prompt_dir: Path | str | None = None) -> dict[str, str]:
    prompts_dir = Path(prompt_dir) if prompt_dir is not None else Path("prompts/agent/reasoning")
    instructions: dict[str, str] = {}
    for role in ("program_planner", "synthesizer"):
        prompt_path = prompts_dir / f"{role}.yaml"
        if prompt_path.exists():
            payload = json.loads(json.dumps(_load_yaml(prompt_path)))
            sections = [
                str(payload["system"]),
                f"Developer guidance: {payload['developer_guidance']}",
                f"Output contract: {payload['output_contract']}",
                "Return only JSON.",
            ]
            instructions[role] = "\n\n".join(sections)
        else:
            instructions[role] = _fallback_instruction(role)
    return instructions


def _execute_step(
    *,
    step: dict[str, Any],
    runtime_inputs: dict[str, Any],
    tool_executor: EvidenceToolExecutor,
    accession_enricher: AccessionEnricher | None,
    accession_cache_dir: str | None,
) -> dict[str, Any]:
    program_type = step["program_type"]
    if program_type == "literature_regrounding":
        query = _literature_query(step=step, runtime_inputs=runtime_inputs)
        tool_runs, _ = tool_executor.execute_requests(
            [{"tool": "search_literature", "parameters": {"query": query}}],
            _tool_evidence(runtime_inputs),
        )
        return {"status": tool_runs[0].get("status"), "tool_runs": tool_runs}
    if program_type == "semantic_bridge_resolution":
        accessions = _collect_accession_terms(step=step, runtime_inputs=runtime_inputs)
        bridge = resolve_semantic_bridge(
            accessions_by_source=accessions,
            accession_enricher=accession_enricher or AccessionEnricher(),
            cache_dir=accession_cache_dir,
        )
        bridge["evidence_ref"] = "TOOL:resolve_semantic_bridge:1"
        return {"status": bridge.get("status"), "tool_runs": [bridge]}
    if program_type == "local_context_discrimination":
        patterns = step.get("focus_terms") or [runtime_inputs["candidate_summary"]["cluster_30"]]
        tool_runs, _ = tool_executor.execute_requests(
            [{"tool": "query_context_features", "parameters": {"patterns": patterns}}],
            _tool_evidence(runtime_inputs),
        )
        return {"status": tool_runs[0].get("status"), "tool_runs": tool_runs}
    if program_type in {
        "cohort_anomaly_scan",
        "subgroup_comparison",
        "architecture_comparison",
        "cross_system_comparison",
    }:
        cohort_candidates = runtime_inputs["occurrence_bundle"].get("candidate_cohort", [])
        top_cluster = _top_focus_cluster(step=step)
        with_pattern = [item for item in cohort_candidates if item.get("cluster_30") == top_cluster]
        without_pattern = [item for item in cohort_candidates if item.get("cluster_30") != top_cluster]
        length_shift = compare_candidate_lengths(with_pattern=with_pattern, without_pattern=without_pattern)
        covariation = compare_neighbor_covariation(candidates=cohort_candidates)
        summary = summarize_cohort_patterns(
            query_id=runtime_inputs["candidate_summary"]["query_id"],
            program_type=program_type,
            length_shift=length_shift,
            covariation=covariation,
        )
        tool_run = {
            "tool": "cohort_investigator",
            "status": "ok",
            "summary": summary,
            "evidence_ref": f"TOOL:cohort_investigator:{program_type}",
        }
        return {"status": "ok", "tool_runs": [tool_run]}
    if program_type == "identity_adjudication":
        tool_runs, _ = tool_executor.execute_requests(
            [{"tool": "summarize_annotations", "parameters": {}}],
            _tool_evidence(runtime_inputs),
        )
        return {"status": tool_runs[0].get("status"), "tool_runs": tool_runs}
    return {"status": "deferred", "tool_runs": []}


def _audit_step(*, step: dict[str, Any], step_result: dict[str, Any]) -> dict[str, Any]:
    status = str(step_result.get("status") or "unresolved")
    evidence_refs = [str(run.get("evidence_ref")) for run in step_result.get("tool_runs", []) if run.get("evidence_ref")]
    verdict = "support" if status == "ok" else "unresolved"
    return {
        "step_id": step.get("step_id"),
        "program_type": step.get("program_type"),
        "verdict": verdict,
        "status": status,
        "rationale": f"Program step {step.get('program_type')} completed with status {status}.",
        "evidence_refs": evidence_refs,
    }


def _update_notebook(
    *,
    notebook: dict[str, Any],
    step: dict[str, Any],
    step_result: dict[str, Any],
    audited_claim: dict[str, Any],
) -> None:
    notebook.setdefault("recent_outcomes", []).append(
        {
            "step_id": step.get("step_id"),
            "program_type": step.get("program_type"),
            "status": step_result.get("status"),
        }
    )
    if step.get("program_type") == "literature_regrounding":
        for run in step_result.get("tool_runs", []):
            if run.get("status") not in {"ok", "skipped"}:
                notebook.setdefault("failed_bridges", []).append(
                    {
                        "program_type": "literature_regrounding",
                        "reason": str(run.get("reason") or run.get("error_type") or "literature failure"),
                    }
                )
    if step.get("program_type") == "semantic_bridge_resolution" and step_result.get("status") == "unresolved":
        notebook.setdefault("failed_bridges", []).append(
            {
                "program_type": "semantic_bridge_resolution",
                "reason": "semantic bridge remained unresolved",
            }
        )
    if audited_claim.get("status") != "ok":
        notebook.setdefault("escalation_signals", []).append(
            f"{step.get('program_type')} did not produce a decisive result"
        )


def _tool_evidence(runtime_inputs: dict[str, Any]) -> dict[str, Any]:
    bundle = runtime_inputs["occurrence_bundle"]
    return {
        "examples": bundle.get("examples", []),
        "sequence_evidence": bundle.get("sequence_evidence", {}),
    }


def _collect_accession_terms(*, step: dict[str, Any], runtime_inputs: dict[str, Any]) -> dict[str, list[str]]:
    patterns = step.get("focus_terms") or []
    pattern_text = " ".join(str(pattern) for pattern in patterns)
    found = {
        "COG": re.findall(r"\bCOG\d+\b", pattern_text),
        "KEGG": re.findall(r"\bK\d+\b", pattern_text),
        "Pfam": re.findall(r"\bPF\d+\b", pattern_text),
        "InterPro": re.findall(r"\bIPR\d+\b", pattern_text),
    }
    if any(found.values()):
        return {source: values for source, values in found.items() if values}
    collected: dict[str, set[str]] = {"COG": set(), "KEGG": set(), "Pfam": set(), "InterPro": set()}
    for example in runtime_inputs["occurrence_bundle"].get("examples", []):
        for item in (example.get("context") or {}).get("context", []):
            protein = item.get("protein") or {}
            for source, field in (("COG", "cog_id"), ("KEGG", "kegg"), ("Pfam", "pfam"), ("InterPro", "interpro")):
                value = protein.get(field)
                if value:
                    for token in re.split(r"[;,|\s]+", str(value)):
                        if token:
                            collected[source].add(token.split(":")[-1])
    return {source: sorted(values) for source, values in collected.items() if values}


def _top_focus_cluster(*, step: dict[str, Any]) -> str | None:
    focus_terms = [str(term) for term in step.get("focus_terms") or []]
    return focus_terms[0] if focus_terms else None


def _literature_query(*, step: dict[str, Any], runtime_inputs: dict[str, Any]) -> str:
    seed = runtime_inputs["seed_summary"]["query_prior"].get("function_description") or runtime_inputs["seed_summary"][
        "query_prior"
    ].get("header_description")
    candidate = runtime_inputs["candidate_neighbor_summary"].get("product") or "candidate neighbor protein"
    focus_terms = " ".join(step.get("focus_terms") or [])
    return " ".join(part for part in [str(seed or "").strip(), focus_terms.strip(), str(candidate).strip()] if part)


def _seed_summary_model(seed_summary: dict[str, Any]):  # noqa: ANN001
    from falcon.reasoning.types import SeedSummary

    return SeedSummary(
        query_id=seed_summary["query_id"],
        query_prior=dict(seed_summary["query_prior"]),
        target_consensus_annotation=dict(seed_summary.get("target_consensus_annotation") or {}),
        note=str(seed_summary.get("note") or ""),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Reasoning prompt must contain a mapping: {path}")
    return payload


def _fallback_instruction(role: str) -> str:
    if role == "program_planner":
        return (
            "Plan the next research program for one candidate. Use seed summary, candidate summary, notebook state, "
            "and occurrence evidence. Return a 1-4 step agenda. Do not invent motif criteria."
        )
    return (
        "Synthesize a conservative supported claim, a notebook summary, an agenda summary, and next program "
        "recommendations. Do not overstate tool results."
    )
