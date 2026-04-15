from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import re

from falcon.agent.loop import run_llm_loop
from falcon.agent.prompts import PromptPack, load_prompt_pack
from falcon.agent.providers import LLMProvider, OpenAIChatProvider, ReplayLLMProvider, ScriptedLLMProvider
from falcon.agent.team import run_team_loop
from falcon.agent.team.events import JsonlEventLogger
from falcon.context.extractor import extract_context
from falcon.data.clusters import ClusterRepository
from falcon.data.proteins import ProteinNotFoundError, ProteinRepository
from falcon.data.sequences import SequenceRepository
from falcon.homology.search import write_jsonl
from falcon.literature.search import DualLiteratureClient, LiteratureClient
from falcon.reporting.markdown import render_agent_report
from falcon.tools.agent_registry import (
    EvidenceToolExecutor,
    build_candidate_mmseqs_runner,
    build_interproscan_runner,
)
from falcon.tools.manifest import ToolManifest, load_tool_manifest


def reason_candidates(
    *,
    candidates_path: Path | str,
    proteins_db: Path | str,
    clusters_db: Path | str,
    protein_manifest: Path | str,
    genome_manifest: Path | str,
    out_dir: Path | str,
    max_candidates: int | None,
    max_examples: int,
    include_sequences: bool,
    flank_bp: int,
    sequence_max_bases: int,
    workflow: str = "deterministic",
    llm_mode: str = "deterministic",
    prompt_pack: Path | str | None = None,
    max_iterations: int = 6,
    max_team_rounds: int = 2,
    team_prompt_dir: Path | str | None = None,
    team_schema_retries: int = 2,
    team_ledger_dir: Path | str = "ledgers",
    tool_manifest_path: Path | str | None = None,
    team_resume: str = "skip_completed",
    max_expensive_tools_per_candidate: int | None = None,
    literature_max_results: int = 5,
    interproscan_policy: str = "on_demand",
    interproscan_path: Path | str | None = None,
    interproscan_threads: int = 1,
    mmseqs_path: Path | str | None = None,
    mmseqs_db_root: Path | str | None = None,
    mmseqs_search_level: int = 90,
    mmseqs_sensitivity: float = 7.5,
    mmseqs_evalue: float = 1e-3,
    mmseqs_max_hits: int = 25,
    mmseqs_threads: int = 1,
    log_dir: Path | str = "logs",
    progress: bool = True,
    heartbeat_seconds: int = 30,
    event_log: Path | str = "agent_events.jsonl",
    llm_model_name: str | None = None,
    llm_base_url: str | None = None,
    llm_api_key_env: str = "OPENAI_API_KEY",
    llm_temperature: float = 0.2,
    llm_max_tokens: int = 2000,
    replay_path: Path | str | None = None,
    llm_provider: LLMProvider | None = None,
    literature_client: LiteratureClient | None = None,
) -> dict[str, Any]:
    output_dir = Path(out_dir)
    reports_dir = output_dir / "reports"
    ledgers_dir = output_dir / Path(team_ledger_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ledgers_dir.mkdir(parents=True, exist_ok=True)
    event_logger = JsonlEventLogger(output_dir / Path(event_log), emit_to_stderr=bool(progress))
    tool_manifest = load_tool_manifest(tool_manifest_path, runner_ids=EvidenceToolExecutor.allowlisted_tools)

    candidates = _read_jsonl(candidates_path)
    if max_candidates is not None:
        candidates = candidates[: int(max_candidates)]

    normalized_workflow = str(workflow)
    normalized_llm_mode = str(llm_mode)
    if normalized_workflow not in {"deterministic", "single", "team"}:
        raise ValueError(f"Unsupported agent.workflow: {normalized_workflow}")
    if normalized_workflow == "deterministic" and normalized_llm_mode != "deterministic":
        normalized_workflow = "single"
    prompt_pack_obj: PromptPack | None = None
    provider: LLMProvider | None = None
    trace_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    team_trace_records: list[dict[str, Any]] = []
    tool_plan_records: list[dict[str, Any]] = []
    tool_result_records: list[dict[str, Any]] = []
    literature_records: list[dict[str, Any]] = []
    if normalized_workflow in {"single", "team"} and normalized_llm_mode == "deterministic":
        raise ValueError(
            f"agent.workflow={normalized_workflow} requires agent.llm.mode to be mock, live, or replay"
        )
    if normalized_llm_mode != "deterministic":
        if normalized_workflow != "team" and prompt_pack is None:
            raise ValueError("agent.llm.prompt_pack must be set when LLM mode is enabled")
        if normalized_workflow != "team":
            prompt_pack_obj = load_prompt_pack(prompt_pack)
        provider = llm_provider or _build_llm_provider(
            mode=normalized_llm_mode,
            model_name=llm_model_name,
            base_url=llm_base_url,
            api_key_env=llm_api_key_env,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            replay_path=replay_path,
        )
    interproscan_runner = build_interproscan_runner(
        interproscan_path=interproscan_path,
        threads=interproscan_threads,
        output_dir=output_dir,
        log_dir=log_dir,
        event_logger=event_logger,
        heartbeat_seconds=heartbeat_seconds,
    )
    candidate_mmseqs_runner = build_candidate_mmseqs_runner(
        mmseqs_path=mmseqs_path,
        mmseqs_db_root=mmseqs_db_root,
        output_dir=output_dir,
        log_dir=log_dir,
        search_level=mmseqs_search_level,
        sensitivity=mmseqs_sensitivity,
        evalue=mmseqs_evalue,
        max_hits=mmseqs_max_hits,
        threads=mmseqs_threads,
        event_logger=event_logger,
        heartbeat_seconds=heartbeat_seconds,
    )
    tool_executor = EvidenceToolExecutor(
        literature_client=literature_client or (DualLiteratureClient() if normalized_workflow == "team" else None),
        interproscan_runner=interproscan_runner,
        mmseqs_runner=candidate_mmseqs_runner,
        tool_manifest=tool_manifest,
        max_expensive_tools_per_candidate=max_expensive_tools_per_candidate,
        event_logger=event_logger,
        literature_max_results=literature_max_results,
        interproscan_policy=interproscan_policy,
    )

    results = []
    with ProteinRepository(proteins_db) as proteins, ClusterRepository(clusters_db) as clusters, SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        for index, candidate in enumerate(candidates, start=1):
            candidate_slug = _candidate_slug(candidate)
            ledger_path = ledgers_dir / f"{index:04d}-{candidate_slug}.json"
            if normalized_workflow == "team" and team_resume == "skip_completed" and _has_completed_ledger(ledger_path):
                event_logger.emit(
                    "candidate_skipped_existing_ledger",
                    candidate_index=index,
                    candidate_slug=candidate_slug,
                    ledger_path=str(ledger_path),
                )
                results.append(
                    {
                        "candidate": _candidate_summary(candidate),
                        "examples": [],
                        "sequence_evidence": {"protein": {"available": False}, "dna": {"available": False}},
                        "falsification_checklist": [],
                        "reasoning": {
                            "status": "skipped",
                            "rationale": "Existing completed candidate ledger was reused.",
                            "evidence": [],
                        },
                        "uncertainties": [],
                        "ledger_path": str(ledger_path),
                        "team_trace": {"workflow": "team", "rounds": 0, "ledger_blocked": False, "resumed": True},
                        "tool_results": [],
                        "literature_evidence": [],
                        "report_path": str(reports_dir / f"{index:04d}-{candidate_slug}.md"),
                    }
                )
                continue
            result = _reason_candidate(
                candidate=candidate,
                candidate_index=index,
                proteins=proteins,
                clusters=clusters,
                sequences=sequences,
                proteins_db=proteins_db,
                clusters_db=clusters_db,
                reports_dir=reports_dir,
                ledgers_dir=ledgers_dir,
                max_examples=max_examples,
                include_sequences=include_sequences,
                flank_bp=flank_bp,
                sequence_max_bases=sequence_max_bases,
                workflow=normalized_workflow,
                llm_mode=normalized_llm_mode,
                prompt_pack=prompt_pack_obj,
                llm_provider=provider,
                max_iterations=max_iterations,
                max_team_rounds=max_team_rounds,
                team_prompt_dir=team_prompt_dir,
                team_schema_retries=team_schema_retries,
                tool_manifest=tool_manifest,
                event_logger=event_logger,
                tool_executor=tool_executor,
            )
            trace_records.extend(result.pop("_agent_trace_records", []))
            call_records.extend(result.pop("_llm_call_records", []))
            team_trace_records.extend(result.pop("_team_trace_records", []))
            tool_plan_records.extend(result.pop("_tool_plan_records", []))
            tool_result_records.extend(result.pop("_tool_result_records", []))
            literature_records.extend(result.pop("_literature_records", []))
            results.append(result)

    results_path = output_dir / "agent_results.jsonl"
    write_jsonl(results, results_path)
    trace_path = output_dir / "agent_trace.jsonl"
    calls_path = output_dir / "llm_calls.jsonl"
    if normalized_llm_mode != "deterministic":
        write_jsonl(trace_records, trace_path)
        write_jsonl(call_records, calls_path)
    team_trace_path = output_dir / "agent_team_trace.jsonl"
    tool_plan_path = output_dir / "tool_plan.jsonl"
    tool_results_path = output_dir / "tool_results.jsonl"
    literature_path = output_dir / "literature_evidence.jsonl"
    if normalized_workflow == "team":
        write_jsonl(team_trace_records, team_trace_path)
        write_jsonl(tool_plan_records, tool_plan_path)
        write_jsonl(tool_result_records, tool_results_path)
        write_jsonl(literature_records, literature_path)
    summary = {
        "candidates_input": str(candidates_path),
        "candidates_processed": len(results),
        "agent_results": str(results_path),
        "reports_dir": str(reports_dir),
        "status_counts": _status_counts(results),
        "llm_mode": normalized_llm_mode,
        "workflow": normalized_workflow,
    }
    if normalized_llm_mode != "deterministic":
        summary["agent_trace"] = str(trace_path)
        summary["llm_calls"] = str(calls_path)
    if normalized_workflow == "team":
        summary["agent_team_trace"] = str(team_trace_path)
        summary["tool_plan"] = str(tool_plan_path)
        summary["tool_results"] = str(tool_results_path)
        summary["literature_evidence"] = str(literature_path)
        summary["candidate_ledgers"] = str(ledgers_dir)
        summary["agent_events"] = str(output_dir / Path(event_log))
    (output_dir / "agent_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _reason_candidate(
    *,
    candidate: dict[str, Any],
    candidate_index: int,
    proteins: ProteinRepository,
    clusters: ClusterRepository,
    sequences: SequenceRepository,
    proteins_db: Path | str,
    clusters_db: Path | str,
    reports_dir: Path,
    ledgers_dir: Path,
    max_examples: int,
    include_sequences: bool,
    flank_bp: int,
    sequence_max_bases: int,
    workflow: str,
    llm_mode: str,
    prompt_pack: PromptPack | None,
    llm_provider: LLMProvider | None,
    max_iterations: int,
    max_team_rounds: int,
    team_prompt_dir: Path | str | None,
    team_schema_retries: int,
    tool_manifest: ToolManifest,
    event_logger: JsonlEventLogger,
    tool_executor: EvidenceToolExecutor,
) -> dict[str, Any]:
    examples = []
    uncertainties = []
    for example in candidate.get("examples", [])[: int(max_examples)]:
        examples.append(
            _hydrate_example(
                example=example,
                proteins=proteins,
                clusters=clusters,
                proteins_db=proteins_db,
                clusters_db=clusters_db,
                uncertainties=uncertainties,
            )
        )

    representative_neighbor_id = _first_neighbor_id(examples)
    sequence_evidence = _sequence_evidence(
        protein_id=representative_neighbor_id,
        sequences=sequences,
        include_sequences=include_sequences,
        flank_bp=flank_bp,
        sequence_max_bases=sequence_max_bases,
        uncertainties=uncertainties,
    )
    checklist = _falsification_checklist(candidate, examples, sequence_evidence)
    reasoning = _rule_based_reasoning(candidate, examples, checklist)
    result: dict[str, Any] = {
        "candidate": _candidate_summary(candidate),
        "examples": examples,
        "sequence_evidence": sequence_evidence,
        "falsification_checklist": checklist,
        "reasoning": reasoning,
        "uncertainties": uncertainties,
    }
    if workflow == "team":
        if llm_provider is None:
            raise ValueError("LLM provider is required for team workflow")
        if sequence_evidence["protein"].get("available") and "sequence" not in sequence_evidence["protein"]:
            sequence_evidence = _sequence_evidence(
                protein_id=representative_neighbor_id,
                sequences=sequences,
                include_sequences=True,
                flank_bp=flank_bp,
                sequence_max_bases=sequence_max_bases,
                uncertainties=uncertainties,
            )
            result["sequence_evidence"] = sequence_evidence
        team_result = run_team_loop(
            candidate_index=candidate_index,
            candidate_slug=_candidate_slug(candidate),
            evidence=result,
            provider=llm_provider,
            tool_executor=tool_executor,
            max_rounds=max_team_rounds,
            prompt_dir=team_prompt_dir,
            schema_retries=team_schema_retries,
        )
        result["reasoning"] = team_result.reasoning
        result["team_trace"] = team_result.team_trace
        result["tool_results"] = team_result.tool_results
        result["literature_evidence"] = team_result.literature_evidence
        result["uncertainties"].extend(team_result.uncertainties)
        result["ledger"] = team_result.ledger
        ledger_path = ledgers_dir / f"{candidate_index:04d}-{_candidate_slug(candidate)}.json"
        ledger_path.write_text(json.dumps(team_result.ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["ledger_path"] = str(ledger_path)
        result["_team_trace_records"] = team_result.role_calls
        result["_tool_plan_records"] = team_result.tool_plan
        result["_tool_result_records"] = team_result.tool_results
        result["_literature_records"] = team_result.literature_evidence
    elif llm_mode != "deterministic":
        if prompt_pack is None or llm_provider is None:
            raise ValueError("LLM prompt pack and provider are required when LLM mode is enabled")
        loop_result = run_llm_loop(
            candidate_index=candidate_index,
            candidate_slug=_candidate_slug(candidate),
            evidence=result,
            provider=llm_provider,
            prompt_pack=prompt_pack,
            max_iterations=max_iterations,
            mode=llm_mode,
        )
        result["reasoning"] = loop_result.reasoning
        result["llm_trace"] = loop_result.trace_summary
        result["uncertainties"].extend(loop_result.uncertainties)
        result["_agent_trace_records"] = loop_result.trace_records
        result["_llm_call_records"] = loop_result.call_records
    report_path = reports_dir / f"{candidate_index:04d}-{_candidate_slug(candidate)}.md"
    result["report_path"] = str(report_path)
    report_path.write_text(render_agent_report(result), encoding="utf-8")
    result.pop("ledger", None)
    return result


def _hydrate_example(
    *,
    example: dict[str, Any],
    proteins: ProteinRepository,
    clusters: ClusterRepository,
    proteins_db: Path | str,
    clusters_db: Path | str,
    uncertainties: list[str],
) -> dict[str, Any]:
    neighbor_id = str(example.get("neighbor_protein", {}).get("protein_id", ""))
    context_protein_id = str(example.get("context_protein_id", ""))
    hydrated: dict[str, Any] = {
        "context_protein_id": context_protein_id,
        "neighbor_protein_id": neighbor_id,
        "relative_index": example.get("relative_index"),
        "supporting_hits": example.get("supporting_hits", []),
    }
    try:
        hydrated["neighbor_protein"] = proteins.get(neighbor_id)
        hydrated["neighbor_clusters"] = clusters.representatives_for_members([neighbor_id]).get(neighbor_id, {})
    except ProteinNotFoundError:
        uncertainties.append(f"Neighbor protein {neighbor_id} was not found in proteins.db")
        hydrated["neighbor_protein"] = example.get("neighbor_protein", {})
        hydrated["neighbor_clusters"] = {}

    if context_protein_id:
        try:
            hydrated["context"] = extract_context(
                protein_id=context_protein_id,
                proteins_db=proteins_db,
                clusters_db=clusters_db,
                include_clusters=True,
            )
        except (ProteinNotFoundError, ValueError) as exc:
            uncertainties.append(f"Context for {context_protein_id} could not be extracted: {exc}")
    return hydrated


def _sequence_evidence(
    *,
    protein_id: str | None,
    sequences: SequenceRepository,
    include_sequences: bool,
    flank_bp: int,
    sequence_max_bases: int,
    uncertainties: list[str],
) -> dict[str, Any]:
    evidence = {
        "protein": {"available": False},
        "dna": {"available": False},
    }
    if not protein_id:
        uncertainties.append("No occurrence neighbor protein ID was available for sequence lookup")
        return evidence

    try:
        protein_record = sequences.get_protein_sequence(protein_id)
        evidence["protein"] = _sequence_summary(protein_record, include_sequences)
    except (OSError, KeyError, ValueError) as exc:
        uncertainties.append(f"Protein sequence for {protein_id} could not be read: {exc}")

    try:
        dna_record = sequences.get_dna_for_protein(
            protein_id,
            flank_bp=flank_bp,
            max_bases=sequence_max_bases,
        )
        evidence["dna"] = _sequence_summary(dna_record, include_sequences)
    except (OSError, KeyError, ValueError) as exc:
        uncertainties.append(f"DNA sequence for {protein_id} could not be read: {exc}")
    return evidence


def _sequence_summary(record: dict[str, Any], include_sequence: bool) -> dict[str, Any]:
    summary = {key: value for key, value in record.items() if key != "sequence"}
    summary["available"] = True
    if include_sequence:
        summary["sequence"] = record["sequence"]
    return summary


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "query_id",
        "cluster_30",
        "presence_contexts",
        "query_contexts",
        "copy_count",
        "presence_rate",
        "background_probability",
        "fold_enrichment",
        "p_value",
        "q_value",
    ]
    return {key: candidate.get(key) for key in keys if key in candidate}


def _falsification_checklist(
    candidate: dict[str, Any],
    examples: list[dict[str, Any]],
    sequence_evidence: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "question": "Is the co-localization signal stronger than the configured statistical threshold?",
            "status": "pass" if float(candidate.get("q_value", 1.0)) <= 0.05 else "unresolved",
            "evidence": f"q_value={candidate.get('q_value')}, fold_enrichment={candidate.get('fold_enrichment')}",
        },
        {
            "question": "Does at least one real occurrence example support this candidate?",
            "status": "pass" if examples else "fail",
            "evidence": f"examples={len(examples)}",
        },
        {
            "question": "Is sequence-level evidence retrievable for follow-up annotation?",
            "status": "pass" if sequence_evidence["protein"]["available"] else "unresolved",
            "evidence": f"protein_sequence_available={sequence_evidence['protein']['available']}",
        },
    ]


def _rule_based_reasoning(
    candidate: dict[str, Any],
    examples: list[dict[str, Any]],
    checklist: list[dict[str, str]],
) -> dict[str, str]:
    q_value = float(candidate.get("q_value", 1.0))
    fold_enrichment = float(candidate.get("fold_enrichment", 0.0))
    presence_contexts = int(candidate.get("presence_contexts", 0))
    has_failure = any(item["status"] == "fail" for item in checklist)
    if has_failure:
        status = "conflicting"
        rationale = "At least one core falsification check failed."
    elif q_value <= 0.05 and fold_enrichment >= 2.0 and presence_contexts >= 3 and examples:
        status = "supported"
        rationale = "Co-localization is statistically strong and backed by occurrence examples."
    elif examples:
        status = "weak"
        rationale = "Occurrence examples exist, but statistical support is below the MVP support threshold."
    else:
        status = "insufficient"
        rationale = "No occurrence-level examples were available for deterministic reasoning."
    return {"status": status, "rationale": rationale}


def _first_neighbor_id(examples: Iterable[dict[str, Any]]) -> str | None:
    for example in examples:
        neighbor_id = example.get("neighbor_protein_id")
        if neighbor_id:
            return str(neighbor_id)
    return None


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _has_completed_ledger(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    final = payload.get("final") if isinstance(payload, dict) else None
    return isinstance(final, dict) and bool(final.get("status"))


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = result["reasoning"]["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _candidate_slug(candidate: dict[str, Any]) -> str:
    raw = f"{candidate.get('query_id', 'query')}-{candidate.get('cluster_30', 'cluster')}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-") or "candidate"


def _build_llm_provider(
    *,
    mode: str,
    model_name: str | None,
    base_url: str | None,
    api_key_env: str,
    temperature: float,
    max_tokens: int,
    replay_path: Path | str | None,
) -> LLMProvider:
    if mode == "mock":
        return ScriptedLLMProvider()
    if mode == "replay":
        if replay_path is None:
            raise ValueError("agent.llm.replay_path must be set for replay LLM mode")
        return ReplayLLMProvider(replay_path)
    if mode == "live":
        return OpenAIChatProvider(
            model_name=model_name,
            api_key_env=api_key_env,
            base_url=base_url,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
    raise ValueError(f"Unsupported agent.llm.mode: {mode}")
