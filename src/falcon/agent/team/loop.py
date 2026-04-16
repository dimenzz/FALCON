from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from falcon.agent.actions import FINAL_STATUSES
from falcon.agent.providers import LLMProvider
from falcon.agent.team.family_naming import resolve_family_naming
from falcon.agent.team.ledger import (
    CandidateLedger,
    add_audit_nodes,
    add_evidence_need_nodes,
    add_falsification_test_nodes,
    add_final_claim_node,
    add_family_selection_node,
    add_dynamic_tool_nodes,
    add_hypothesis_nodes,
    add_literature_records,
    add_literature_summary_nodes,
    add_revision_node,
    add_tool_plan_validation_nodes,
    add_tool_request_nodes,
    add_tool_observations,
    add_tool_summary_nodes,
    initialize_ledger,
    mark_blocked,
)
from falcon.agent.team.tool_summaries import summarize_tool_results
from falcon.agent.team.context_pack import build_role_context_pack
from falcon.agent.team.roles import (
    dynamic_tool_designer,
    dynamic_tool_reviewer,
    evidence_auditor,
    evidence_needs,
    hypothesis_generator,
    hypothesis_reviser,
    literature_scout,
    synthesizer,
    tool_planner,
)
from falcon.agent.team.roles.base import RoleOutputError, RoleRunner
from falcon.tools.agent_registry import EvidenceToolExecutor
from falcon.tools.accession_enrichment import AccessionEnricher
from falcon.tools.manifest import ToolManifest, default_tool_manifest
from falcon.tools.plan_validator import ToolPlanValidator

TEAM_ROLES = (
    "literature_scout",
    "hypothesis_generator",
    "evidence_needs",
    "tool_planner",
    "dynamic_tool_designer",
    "dynamic_tool_reviewer",
    "evidence_auditor",
    "hypothesis_reviser",
    "synthesizer",
)


@dataclass(frozen=True)
class TeamLoopResult:
    reasoning: dict[str, Any]
    team_trace: dict[str, Any]
    role_calls: list[dict[str, Any]]
    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    literature_evidence: list[dict[str, Any]]
    uncertainties: list[str]
    ledger: CandidateLedger


def run_team_loop(
    *,
    candidate_index: int,
    candidate_slug: str,
    evidence: dict[str, Any],
    provider: LLMProvider,
    tool_executor: EvidenceToolExecutor,
    max_rounds: int,
    prompt_dir: Path | str | None = None,
    schema_retries: int = 2,
    tool_manifest: ToolManifest | None = None,
    event_logger: Any | None = None,
    dynamic_tools_enabled: bool = False,
    dynamic_tool_runner: Any | None = None,
    accession_enricher: AccessionEnricher | None = None,
    accession_cache_dir: str | None = None,
) -> TeamLoopResult:
    role_calls: list[dict[str, Any]] = []
    ledger = initialize_ledger(candidate_index=candidate_index, candidate_slug=candidate_slug, evidence=evidence)
    manifest = tool_manifest or default_tool_manifest()
    runner = RoleRunner(
        provider=provider,
        role_instructions=load_team_role_instructions(prompt_dir),
        candidate_index=candidate_index,
        candidate_slug=candidate_slug,
        schema_retries=schema_retries,
        role_calls=role_calls,
        event_logger=event_logger,
    )

    try:
        _emit_event(event_logger, "candidate_started", candidate_slug=candidate_slug, candidate_index=candidate_index)
        _run_family_naming(
            ledger=ledger,
            evidence=evidence,
            accession_enricher=accession_enricher or AccessionEnricher(),
            accession_cache_dir=accession_cache_dir,
        )
        _run_literature_grounding(
            runner,
            tool_executor,
            evidence,
            ledger,
            tool_manifest=manifest,
            dynamic_tools_enabled=dynamic_tools_enabled,
        )
        _run_hypothesis_and_evidence_planning(
            runner,
            ledger,
            evidence=evidence,
            tool_manifest=manifest,
            dynamic_tools_enabled=dynamic_tools_enabled,
        )
        for round_index in range(1, max(1, int(max_rounds)) + 1):
            ledger["active_round"] = round_index
            plan = tool_planner.plan(
                runner,
                _with_task_context(
                    build_role_context_pack(
                        role="tool_planner",
                        ledger=ledger,
                        evidence=evidence,
                        tool_manifest=manifest,
                        dynamic_tools_enabled=dynamic_tools_enabled,
                    ),
                    round=round_index,
                ),
            )
            tool_requests = [request.model_dump(mode="json") for request in plan.tool_requests]
            ledger["tool_plan"].extend(tool_requests)
            add_tool_request_nodes(ledger, tool_requests, created_by="tool_planner")
            if plan.skipped_needs:
                ledger["skipped_evidence_needs"] = [item.model_dump(mode="json") for item in plan.skipped_needs]
            tool_requests, validation_records = ToolPlanValidator(manifest).validate(
                tool_requests,
                evidence_needs=ledger.get("evidence_needs", []),
            )
            if validation_records:
                add_tool_plan_validation_nodes(ledger, validation_records, created_by="tool_plan_validator")
            rejected_tool_observations = [
                {
                    "tool": validation.get("tool"),
                    "status": "rejected",
                    "reason": validation.get("reason"),
                    "evidence_need_id": validation.get("evidence_need_id"),
                }
                for validation in validation_records
                if validation.get("status") == "rejected"
            ]
            if rejected_tool_observations:
                add_tool_observations(ledger, rejected_tool_observations)
            tool_results, literature_records = tool_executor.execute_requests(
                tool_requests,
                evidence,
                event_context={"candidate_slug": candidate_slug, "candidate_index": candidate_index, "round": round_index},
            )
            for request, result in zip(tool_requests, tool_results):
                result.setdefault("request_id", request.get("request_id"))
                result.setdefault("evidence_need_id", request.get("evidence_need_id"))
            add_tool_observations(ledger, tool_results)
            tool_summaries = summarize_tool_results(
                tool_results=tool_results,
                tool_manifest=manifest,
                existing_summaries=ledger.get("tool_summaries", []),
            )
            add_tool_summary_nodes(ledger, tool_summaries, created_by="tool_scheduler")
            add_literature_records(ledger, literature_records)
            if dynamic_tools_enabled and dynamic_tool_runner is not None:
                dynamic_records = _run_dynamic_tool_fallbacks(
                    runner,
                    ledger,
                    evidence=evidence,
                    tool_manifest=manifest,
                    validation_records=validation_records,
                    dynamic_tool_runner=dynamic_tool_runner,
                )
                if dynamic_records:
                    add_dynamic_tool_nodes(ledger, dynamic_records, created_by="dynamic_tool_runner")
                    add_tool_observations(
                        ledger,
                        [record["result"] for record in dynamic_records if record.get("node_type") == "dynamic_tool_result"],
                    )

            audit = evidence_auditor.audit(
                runner,
                _with_task_context(
                    build_role_context_pack(
                        role="evidence_auditor",
                        ledger=ledger,
                        evidence=evidence,
                        tool_manifest=manifest,
                        dynamic_tools_enabled=dynamic_tools_enabled,
                    ),
                    round=round_index,
                ),
            )
            audit_findings = [finding.model_dump(mode="json") for finding in audit.audits]
            ledger["audit"]["findings"].extend(audit_findings)
            add_audit_nodes(ledger, audit_findings, created_by="evidence_auditor")

            revision = hypothesis_reviser.revise(
                runner,
                _with_task_context(
                    build_role_context_pack(
                        role="hypothesis_reviser",
                        ledger=ledger,
                        evidence=evidence,
                        tool_manifest=manifest,
                        dynamic_tools_enabled=dynamic_tools_enabled,
                    ),
                    round=round_index,
                ),
            )
            revision_payload = revision.model_dump(mode="json")
            ledger["revisions"].append(revision_payload)
            add_revision_node(ledger, revision_payload, created_by="hypothesis_reviser")
            ledger["contradiction_ledger"].extend(revision.contradictions)
            if revision.revised_hypotheses:
                revised_hypotheses = [hypothesis.model_dump(mode="json") for hypothesis in revision.revised_hypotheses]
                ledger["hypotheses"].extend(revised_hypotheses)
                add_hypothesis_nodes(ledger, revised_hypotheses, created_by="hypothesis_reviser")
            if revision.rejected_hypotheses:
                ledger["rejected_hypotheses"] = [item.model_dump(mode="json") for item in revision.rejected_hypotheses]

    except RoleOutputError as exc:
        mark_blocked(ledger, role=exc.role, attempts=exc.attempts, error=exc.message)
    finally:
        _emit_event(event_logger, "candidate_finished", candidate_slug=candidate_slug, candidate_index=candidate_index)

    reasoning = _run_synthesis(
        runner,
        ledger,
        evidence=evidence,
        tool_manifest=manifest,
        dynamic_tools_enabled=dynamic_tools_enabled,
    )
    return _team_result(ledger=ledger, role_calls=role_calls, reasoning=reasoning)


def _run_literature_grounding(
    runner: RoleRunner,
    tool_executor: EvidenceToolExecutor,
    evidence: dict[str, Any],
    ledger: CandidateLedger,
    tool_manifest: ToolManifest,
    dynamic_tools_enabled: bool,
) -> None:
    plan = literature_scout.plan_queries(
        runner,
        _with_task_context(
            build_role_context_pack(
                role="literature_scout",
                ledger=ledger,
                evidence=evidence,
                tool_manifest=tool_manifest,
                dynamic_tools_enabled=dynamic_tools_enabled,
            ),
            task="plan_literature_queries",
        ),
    )
    ledger["literature"]["queries"] = list(plan.queries)
    query_requests = [
        {
            "tool": "search_literature",
            "reason": plan.rationale,
            "parameters": {"query": query},
        }
        for query in plan.queries
    ]
    query_results, literature_records = tool_executor.execute_requests(query_requests, evidence)
    failed_queries = [
        result
        for result in query_results
        if result.get("tool") == "search_literature" and result.get("status") not in {"ok", "skipped"}
    ]
    add_tool_observations(ledger, query_results)
    add_literature_records(ledger, literature_records)
    ledger["literature"]["failed_queries"] = failed_queries

    brief = literature_scout.write_brief(
        runner,
        _with_task_context(
            build_role_context_pack(
                role="literature_scout",
                ledger=ledger,
                evidence=evidence,
                tool_manifest=tool_manifest,
                dynamic_tools_enabled=dynamic_tools_enabled,
            ),
            task="write_literature_brief",
        ),
    )
    brief_payload = brief.model_dump(mode="json")
    summaries = list(brief_payload.get("summaries", []))
    ledger["literature"]["brief"] = {
        "summary": summaries[0].get("summary", "") if summaries else brief_payload.get("summary", ""),
        "key_findings": summaries[0].get("key_findings", []) if summaries else brief_payload.get("key_findings", []),
        "constraints": summaries[0].get("constraints", []) if summaries else brief_payload.get("constraints", []),
        "citation_refs": summaries[0].get("citation_refs", []) if summaries else brief_payload.get("citation_refs", []),
    }
    ledger["literature"]["scoped_summaries"] = summaries
    add_literature_summary_nodes(ledger, summaries, created_by="literature_scout")


def _run_family_naming(
    *,
    ledger: CandidateLedger,
    evidence: dict[str, Any],
    accession_enricher: AccessionEnricher,
    accession_cache_dir: str | None,
) -> None:
    representative_neighbor = _representative_neighbor(evidence=evidence, ledger=ledger)
    family_naming = resolve_family_naming(
        representative_neighbor=representative_neighbor,
        accession_enricher=accession_enricher,
        accession_cache_dir=accession_cache_dir,
    )
    ledger["family_naming"] = family_naming
    add_family_selection_node(ledger, family_naming, created_by="family_selector")


def _run_hypothesis_and_evidence_planning(
    runner: RoleRunner,
    ledger: CandidateLedger,
    *,
    evidence: dict[str, Any],
    tool_manifest: ToolManifest,
    dynamic_tools_enabled: bool,
) -> None:
    hypotheses = hypothesis_generator.generate(
        runner,
        build_role_context_pack(
            role="hypothesis_generator",
            ledger=ledger,
            evidence=evidence,
            tool_manifest=tool_manifest,
            dynamic_tools_enabled=dynamic_tools_enabled,
        ),
    )
    ledger["hypotheses"] = [hypothesis.model_dump(mode="json") for hypothesis in hypotheses.hypotheses]
    add_hypothesis_nodes(ledger, ledger["hypotheses"], created_by="hypothesis_generator")

    needs = evidence_needs.derive(
        runner,
        build_role_context_pack(
            role="evidence_needs",
            ledger=ledger,
            evidence=evidence,
            tool_manifest=tool_manifest,
            dynamic_tools_enabled=dynamic_tools_enabled,
        ),
    )
    tests = [test.model_dump(mode="json") for test in needs.tests]
    ledger["falsification_tests"] = tests
    add_falsification_test_nodes(ledger, tests, created_by="evidence_needs")
    ledger["evidence_needs"] = [
        {
            "id": f"N{index}",
            "test_id": test["id"],
            "hypothesis_id": test["hypothesis_id"],
            "evidence_needed": test["evidence_needed"],
            "question": test["question"],
            "suggested_tools": test["suggested_tools"],
        }
        for index, test in enumerate(tests, start=1)
    ]
    add_evidence_need_nodes(ledger, ledger["evidence_needs"], created_by="evidence_needs")


def _run_dynamic_tool_fallbacks(
    runner: RoleRunner,
    ledger: CandidateLedger,
    *,
    evidence: dict[str, Any],
    tool_manifest: ToolManifest,
    validation_records: list[dict[str, Any]],
    dynamic_tool_runner: Any,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target_needs = _dynamic_fallback_targets(
        ledger.get("evidence_needs", []),
        validation_records,
        ledger.get("skipped_evidence_needs", []),
    )
    for target in target_needs:
        design_payload = _with_task_context(
            build_role_context_pack(
                role="dynamic_tool_designer",
                ledger=ledger,
                evidence=evidence,
                tool_manifest=tool_manifest,
                dynamic_tools_enabled=True,
            ),
            target_evidence_need=target,
        )
        try:
            design = dynamic_tool_designer.design(runner, design_payload)
            design_record = design.model_dump(mode="json")
            design_record["node_type"] = "dynamic_tool_spec"
            records.append(design_record)
            review = dynamic_tool_reviewer.review(
                runner,
                _with_task_context(
                    build_role_context_pack(
                        role="dynamic_tool_reviewer",
                        ledger=ledger,
                        evidence=evidence,
                        tool_manifest=tool_manifest,
                        dynamic_tools_enabled=True,
                    ),
                    target_evidence_need=target,
                    dynamic_tool_design=design_record,
                ),
            )
            review_record = review.model_dump(mode="json")
            review_record["node_type"] = "dynamic_tool_review"
            review_record["evidence_need_id"] = target.get("test_id") or target.get("id")
            records.append(review_record)
            if not review.approved:
                continue
            result = dynamic_tool_runner.run(
                script_source=design.script_source,
                input_payload={
                    "evidence": evidence,
                    "ledger": ledger,
                    "context_workbench": design_payload["context_workbench"],
                    "target_evidence_need": target,
                },
                label=str(target.get("test_id") or target.get("id") or "dynamic-tool"),
            )
            records.append(
                {
                    "node_type": "dynamic_tool_result",
                    "evidence_need_id": target.get("test_id") or target.get("id"),
                    "result": result,
                }
            )
        except RoleOutputError as exc:
            records.append(
                {
                    "node_type": "dynamic_tool_result",
                    "evidence_need_id": target.get("test_id") or target.get("id"),
                    "result": {
                        "tool": "dynamic_python",
                        "status": "error",
                        "reason": str(exc),
                    },
                }
            )
    return records


def _dynamic_fallback_targets(
    evidence_needs: list[dict[str, Any]],
    validation_records: list[dict[str, Any]],
    skipped_needs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    need_ids = {
        str(record.get("evidence_need_id"))
        for record in validation_records
        if record.get("status") == "rejected"
        and any(token in str(record.get("reason") or "") for token in ("capability mismatch", "not in manifest"))
    }
    skipped_needs = skipped_needs or []
    skipped_need_text = {
        str(item.get("evidence_needed") or "")
        for item in skipped_needs
        if any(token in str(item.get("reason") or "") for token in ("unsupported", "dynamic", "no available tool"))
    }
    targets = []
    for need in evidence_needs:
        need_id = str(need.get("test_id") or need.get("id") or "")
        if need_id in need_ids or str(need.get("evidence_needed") or "") in skipped_need_text:
            targets.append(need)
    return targets


def _run_synthesis(
    runner: RoleRunner,
    ledger: CandidateLedger,
    *,
    evidence: dict[str, Any],
    tool_manifest: ToolManifest,
    dynamic_tools_enabled: bool,
) -> dict[str, Any]:
    try:
        synthesis = synthesizer.synthesize(
            runner,
            _with_task_context(
                build_role_context_pack(
                    role="synthesizer",
                    ledger=ledger,
                    evidence=evidence,
                    tool_manifest=tool_manifest,
                    dynamic_tools_enabled=dynamic_tools_enabled,
                ),
                blocked_step=ledger.get("blocked_step"),
            ),
        )
        final = synthesis.model_dump(mode="json")
    except RoleOutputError as exc:
        mark_blocked(ledger, role=exc.role, attempts=exc.attempts, error=exc.message)
        final = {
            "status": "incomplete",
            "rationale": "Synthesis failed schema validation.",
            "evidence_refs": [],
            "accepted_hypotheses": [],
            "rejected_hypotheses": [],
            "unresolved_hypotheses": [hypothesis.get("id") for hypothesis in ledger.get("hypotheses", [])],
            "uncertainties": [str(exc)],
        }
    status = str(final.get("status") or "insufficient")
    if status not in FINAL_STATUSES:
        status = "insufficient"
    final["status"] = status
    ledger["final"] = final
    add_final_claim_node(ledger, final, created_by="synthesizer")
    return {
        "status": status,
        "rationale": str(final.get("rationale") or "No synthesis rationale was provided."),
        "evidence": _string_list(final.get("evidence_refs")),
        "supported_claim": dict(final.get("supported_claim") or {}),
        "working_hypotheses": list(final.get("working_hypotheses") or []),
        "next_evidence_plan": _string_list(final.get("next_evidence_plan")),
    }


def _team_result(
    *,
    ledger: CandidateLedger,
    role_calls: list[dict[str, Any]],
    reasoning: dict[str, Any],
) -> TeamLoopResult:
    return TeamLoopResult(
        reasoning=reasoning,
        team_trace={
            "workflow": "team",
            "rounds": int(ledger.get("active_round", 0)),
            "ledger_blocked": "blocked_step" in ledger,
            "contradictions": ledger.get("contradiction_ledger", []),
            "critic_approved": "blocked_step" not in ledger,
            "hypotheses": ledger.get("hypotheses", []),
            "criticisms": ledger.get("contradiction_ledger", []),
            "blocked_step": ledger.get("blocked_step"),
        },
        role_calls=role_calls,
        tool_plan=ledger.get("tool_plan", []),
        tool_results=ledger.get("tool_observations", []),
        literature_evidence=ledger.get("literature", {}).get("records", []),
        uncertainties=[
            *(_string_list(ledger.get("uncertainties"))),
            *(_string_list(ledger.get("final", {}).get("uncertainties"))),
        ],
        ledger=ledger,
    )


def _representative_neighbor(*, evidence: dict[str, Any], ledger: CandidateLedger) -> dict[str, Any]:
    examples = evidence.get("examples") or ledger.get("examples") or []
    if examples:
        example = examples[0]
        neighbor = dict(example.get("neighbor_protein") or {})
        neighbor.setdefault("protein_id", example.get("neighbor_protein_id"))
        return neighbor
    protein = dict((ledger.get("sequence_evidence") or {}).get("protein") or {})
    if protein:
        protein.setdefault("protein_id", protein.get("protein_id"))
    return protein


def load_team_role_instructions(prompt_dir: Path | str | None = None) -> dict[str, str]:
    if prompt_dir is None:
        return {role: _role_instruction(role) for role in TEAM_ROLES}

    prompts_dir = Path(prompt_dir)
    instructions: dict[str, str] = {}
    for role in TEAM_ROLES:
        prompt_path = prompts_dir / f"{role}.yaml"
        if not prompt_path.exists():
            instructions[role] = _role_instruction(role)
            continue
        payload = yaml.safe_load(prompt_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Team prompt must contain a YAML mapping: {prompt_path}")
        missing = [field for field in ("role", "system", "developer_guidance", "output_contract") if field not in payload]
        if missing:
            raise ValueError(f"Team prompt {prompt_path} is missing required fields: {', '.join(missing)}")
        if str(payload["role"]) != role:
            raise ValueError(f"Team prompt {prompt_path} declares role {payload['role']!r}, expected {role!r}")
        sections = [
            str(payload["system"]),
            f"Developer guidance: {payload['developer_guidance']}",
        ]
        if payload.get("context_requirements"):
            sections.append(f"Context requirements:\n{_format_prompt_list(payload['context_requirements'])}")
        if payload.get("few_shot_antipatterns"):
            sections.append(f"Anti-patterns:\n{_format_prompt_list(payload['few_shot_antipatterns'])}")
        sections.extend(
            [
                f"Output contract: {payload['output_contract']}",
                "Return only JSON.",
            ]
        )
        instructions[role] = "\n\n".join(sections)
    return instructions


def _format_prompt_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return f"- {value}"


def _role_instruction(role: str) -> str:
    instructions = {
        "literature_scout": (
            "Plan literature searches first, then summarize retrieved records. "
            "Do not assign function from literature alone. Return only JSON."
        ),
        "hypothesis_generator": (
            "Generate falsifiable candidate-specific hypotheses grounded in literature and occurrence evidence. "
            "Do not treat neighbor annotations as direct candidate annotations. Return only JSON."
        ),
        "evidence_needs": (
            "For each hypothesis, derive hypothesis-specific falsification tests and evidence needs. "
            "Every test must belong to a hypothesis id. Return only JSON."
        ),
        "tool_planner": (
            "Map evidence needs to tools by reading context_workbench.tool_catalog. "
            "Do not rely on tool names from memory; use only manifest ids in the payload. Return only JSON."
        ),
        "dynamic_tool_designer": (
            "Design a read-only Python dynamic tool only from context_workbench.data_contracts, "
            "artifact_index, and dynamic_tool_contract. Return only JSON."
        ),
        "dynamic_tool_reviewer": (
            "Review a proposed dynamic Python tool against context_workbench.dynamic_tool_contract. "
            "Approve only read-only scripts with valid JSON outputs. Return only JSON."
        ),
        "evidence_auditor": (
            "Audit each falsification test against the collected evidence refs. "
            "Mark support, weaken, falsify, unresolved, or conflicting. Return only JSON."
        ),
        "hypothesis_reviser": (
            "Revise, retain, merge, or reject hypotheses based on audit findings and contradictions. Return only JSON."
        ),
        "synthesizer": (
            "Produce the final conservative conclusion from the ledger only, with evidence refs and uncertainties. "
            "Return only JSON."
        ),
    }
    return instructions[role]


def _compact_examples(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "context_protein_id": example.get("context_protein_id"),
            "neighbor_protein_id": example.get("neighbor_protein_id"),
            "neighbor_product": (example.get("neighbor_protein") or {}).get("product"),
            "relative_index": example.get("relative_index"),
        }
        for example in evidence.get("examples", [])
    ]


def _compact_ledger_for_role(ledger: CandidateLedger) -> dict[str, Any]:
    return {
        "candidate": ledger.get("candidate", {}),
        "deterministic_checks": ledger.get("deterministic_checks", []),
        "literature": ledger.get("literature", {}),
        "hypotheses": ledger.get("hypotheses", []),
        "falsification_tests": ledger.get("falsification_tests", []),
        "tool_plan": ledger.get("tool_plan", []),
        "tool_observations": ledger.get("tool_observations", []),
        "audit": ledger.get("audit", {}),
        "revisions": ledger.get("revisions", []),
        "contradiction_ledger": ledger.get("contradiction_ledger", []),
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _with_task_context(context: dict[str, Any], **extra: Any) -> dict[str, Any]:
    merged = dict(context)
    merged.update(extra)
    return merged


def _emit_event(event_logger: Any | None, event: str, **payload: Any) -> None:
    if event_logger is not None:
        event_logger.emit(event, **payload)
