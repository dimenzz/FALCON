from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from falcon.agent.actions import FINAL_STATUSES
from falcon.agent.providers import LLMProvider
from falcon.agent.team.ledger import (
    CandidateLedger,
    add_literature_records,
    add_tool_observations,
    initialize_ledger,
    mark_blocked,
)
from falcon.agent.team.roles import (
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

TEAM_ROLES = (
    "literature_scout",
    "hypothesis_generator",
    "evidence_needs",
    "tool_planner",
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
) -> TeamLoopResult:
    role_calls: list[dict[str, Any]] = []
    ledger = initialize_ledger(candidate_index=candidate_index, candidate_slug=candidate_slug, evidence=evidence)
    runner = RoleRunner(
        provider=provider,
        role_instructions=load_team_role_instructions(prompt_dir),
        candidate_index=candidate_index,
        candidate_slug=candidate_slug,
        schema_retries=schema_retries,
        role_calls=role_calls,
    )

    try:
        _run_literature_grounding(runner, tool_executor, evidence, ledger)
        _run_hypothesis_and_evidence_planning(runner, ledger)
        for round_index in range(1, max(1, int(max_rounds)) + 1):
            ledger["active_round"] = round_index
            plan = tool_planner.plan(
                runner,
                {
                    "round": round_index,
                    "candidate": ledger["candidate"],
                    "hypotheses": ledger["hypotheses"],
                    "falsification_tests": ledger["falsification_tests"],
                    "evidence_needs": ledger["evidence_needs"],
                    "available_tools": sorted(EvidenceToolExecutor.allowlisted_tools),
                    "ledger_snapshot": _compact_ledger_for_role(ledger),
                },
            )
            ledger["tool_plan"].extend([request.model_dump(mode="json") for request in plan.tool_requests])
            if plan.skipped_needs:
                ledger["skipped_evidence_needs"] = [item.model_dump(mode="json") for item in plan.skipped_needs]
            tool_results, literature_records = tool_executor.execute_requests(
                [request.model_dump(mode="json") for request in plan.tool_requests],
                evidence,
            )
            add_tool_observations(ledger, tool_results)
            add_literature_records(ledger, literature_records)

            audit = evidence_auditor.audit(
                runner,
                {
                    "round": round_index,
                    "candidate": ledger["candidate"],
                    "hypotheses": ledger["hypotheses"],
                    "falsification_tests": ledger["falsification_tests"],
                    "tool_observations": ledger["tool_observations"],
                    "literature": ledger["literature"],
                },
            )
            ledger["audit"]["findings"].extend([finding.model_dump(mode="json") for finding in audit.audits])

            revision = hypothesis_reviser.revise(
                runner,
                {
                    "round": round_index,
                    "candidate": ledger["candidate"],
                    "hypotheses": ledger["hypotheses"],
                    "audit": ledger["audit"],
                    "tool_observations": ledger["tool_observations"],
                    "literature": ledger["literature"],
                },
            )
            ledger["revisions"].append(revision.model_dump(mode="json"))
            ledger["contradiction_ledger"].extend(revision.contradictions)
            if revision.revised_hypotheses:
                ledger["hypotheses"].extend([hypothesis.model_dump(mode="json") for hypothesis in revision.revised_hypotheses])
            if revision.rejected_hypotheses:
                ledger["rejected_hypotheses"] = [item.model_dump(mode="json") for item in revision.rejected_hypotheses]

    except RoleOutputError as exc:
        mark_blocked(ledger, role=exc.role, attempts=exc.attempts, error=exc.message)

    reasoning = _run_synthesis(runner, ledger)
    return _team_result(ledger=ledger, role_calls=role_calls, reasoning=reasoning)


def _run_literature_grounding(
    runner: RoleRunner,
    tool_executor: EvidenceToolExecutor,
    evidence: dict[str, Any],
    ledger: CandidateLedger,
) -> None:
    plan = literature_scout.plan_queries(
        runner,
        {
            "task": "plan_literature_queries",
            "candidate": ledger["candidate"],
            "examples": _compact_examples(evidence),
            "deterministic_checks": ledger["deterministic_checks"],
        },
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
        {
            "task": "write_literature_brief",
            "candidate": ledger["candidate"],
            "queries": ledger["literature"]["queries"],
            "records": ledger["literature"]["records"],
            "failed_queries": failed_queries,
        },
    )
    ledger["literature"]["brief"] = brief.model_dump(mode="json")


def _run_hypothesis_and_evidence_planning(runner: RoleRunner, ledger: CandidateLedger) -> None:
    hypotheses = hypothesis_generator.generate(
        runner,
        {
            "candidate": ledger["candidate"],
            "deterministic_checks": ledger["deterministic_checks"],
            "literature": ledger["literature"],
            "examples": ledger["examples"],
        },
    )
    ledger["hypotheses"] = [hypothesis.model_dump(mode="json") for hypothesis in hypotheses.hypotheses]

    needs = evidence_needs.derive(
        runner,
        {
            "candidate": ledger["candidate"],
            "hypotheses": ledger["hypotheses"],
            "literature": ledger["literature"],
            "deterministic_checks": ledger["deterministic_checks"],
            "available_tools": sorted(EvidenceToolExecutor.allowlisted_tools),
        },
    )
    tests = [test.model_dump(mode="json") for test in needs.tests]
    ledger["falsification_tests"] = tests
    ledger["evidence_needs"] = [
        {
            "test_id": test["id"],
            "hypothesis_id": test["hypothesis_id"],
            "evidence_needed": test["evidence_needed"],
            "suggested_tools": test["suggested_tools"],
        }
        for test in tests
    ]


def _run_synthesis(runner: RoleRunner, ledger: CandidateLedger) -> dict[str, Any]:
    try:
        synthesis = synthesizer.synthesize(
            runner,
            {
                "candidate": ledger["candidate"],
                "ledger": _compact_ledger_for_role(ledger),
                "blocked_step": ledger.get("blocked_step"),
            },
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
    return {
        "status": status,
        "rationale": str(final.get("rationale") or "No synthesis rationale was provided."),
        "evidence": _string_list(final.get("evidence_refs")),
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
        instructions[role] = "\n\n".join(
            [
                str(payload["system"]),
                f"Developer guidance: {payload['developer_guidance']}",
                f"Output contract: {payload['output_contract']}",
                "Return only JSON.",
            ]
        )
    return instructions


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
            "Map evidence needs to allowlisted tools only: search_literature, inspect_context, "
            "summarize_annotations, run_interproscan, run_candidate_mmseqs. Return only JSON."
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
