from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import re

from falcon.agent.providers import LLMProvider, OpenAIChatProvider, ReplayLLMProvider, ScriptedLLMProvider
from falcon.agent.team.events import JsonlEventLogger
from falcon.context.extractor import extract_context
from falcon.data.clusters import ClusterRepository
from falcon.data.proteins import ProteinNotFoundError, ProteinRepository
from falcon.data.sequences import SequenceRepository
from falcon.homology.search import write_jsonl
from falcon.literature.search import DualLiteratureClient, LiteratureClient
from falcon.reasoning.query_catalog import load_query_catalog
from falcon.reasoning.runtime import run_research_runtime
from falcon.reasoning.types import SeedSummary
from falcon.reporting.markdown import render_agent_report
from falcon.tools.accession_enrichment import AccessionEnricher
from falcon.tools.agent_registry import EvidenceToolExecutor, build_candidate_mmseqs_runner, build_interproscan_runner
from falcon.tools.manifest import load_tool_manifest


def reason_candidates(
    *,
    candidates_path: Path | str,
    query_catalog_path: Path | str,
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
    llm_mode: str = "mock",
    max_rounds: int = 2,
    prompt_dir: Path | str | None = None,
    schema_retries: int = 2,
    ledger_dir: Path | str = "ledgers",
    tool_manifest_path: Path | str | None = None,
    max_expensive_tools_per_candidate: int | None = None,
    dynamic_tools_enabled: bool = False,  # kept for config continuity; runtime ignores it for now
    dynamic_tool_timeout: int = 60,  # kept for config continuity; runtime ignores it for now
    dynamic_tool_allowed_imports: list[str] | None = None,  # kept for config continuity; runtime ignores it
    accession_cache_dir: Path | str = "cache",
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
    del dynamic_tools_enabled, dynamic_tool_timeout, dynamic_tool_allowed_imports

    output_dir = Path(out_dir)
    reports_dir = output_dir / "reports"
    ledgers_dir = output_dir / Path(ledger_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ledgers_dir.mkdir(parents=True, exist_ok=True)

    normalized_llm_mode = str(llm_mode)
    if normalized_llm_mode == "deterministic":
        raise ValueError(
            "agent.llm.mode=deterministic was removed. Use mock, live, or replay with the program-driven runtime."
        )

    event_logger = JsonlEventLogger(output_dir / Path(event_log), emit_to_stderr=bool(progress))
    tool_manifest = load_tool_manifest(tool_manifest_path, runner_ids=EvidenceToolExecutor.allowlisted_tools)
    provider = llm_provider or _build_llm_provider(
        mode=normalized_llm_mode,
        model_name=llm_model_name,
        base_url=llm_base_url,
        api_key_env=llm_api_key_env,
        temperature=llm_temperature,
        max_tokens=llm_max_tokens,
        replay_path=replay_path,
    )

    candidates = _read_jsonl(candidates_path)
    if max_candidates is not None:
        candidates = candidates[: int(max_candidates)]
    query_catalog = load_query_catalog(query_catalog_path)
    candidate_cohort = [_candidate_cohort_row(record) for record in candidates]

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
        literature_client=literature_client or DualLiteratureClient(),
        interproscan_runner=interproscan_runner,
        mmseqs_runner=candidate_mmseqs_runner,
        tool_manifest=tool_manifest,
        max_expensive_tools_per_candidate=max_expensive_tools_per_candidate,
        event_logger=event_logger,
        literature_max_results=literature_max_results,
        interproscan_policy=interproscan_policy,
    )
    accession_enricher = AccessionEnricher()

    results: list[dict[str, Any]] = []
    program_trace_records: list[dict[str, Any]] = []
    tool_result_records: list[dict[str, Any]] = []
    with ProteinRepository(proteins_db) as proteins, ClusterRepository(clusters_db) as clusters, SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        for index, candidate in enumerate(candidates, start=1):
            result = _reason_candidate(
                candidate=candidate,
                candidate_index=index,
                query_catalog=query_catalog,
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
                llm_provider=provider,
                max_rounds=max_rounds,
                prompt_dir=prompt_dir,
                schema_retries=schema_retries,
                event_logger=event_logger,
                tool_executor=tool_executor,
                accession_enricher=accession_enricher,
                accession_cache_dir=str(accession_cache_dir),
                candidate_cohort=candidate_cohort,
            )
            program_trace_records.extend(result.pop("_program_trace_records", []))
            tool_result_records.extend(result.pop("_tool_result_records", []))
            results.append(result)

    results_path = output_dir / "agent_results.jsonl"
    write_jsonl(results, results_path)
    program_trace_path = output_dir / "program_trace.jsonl"
    tool_results_path = output_dir / "tool_results.jsonl"
    write_jsonl(program_trace_records, program_trace_path)
    write_jsonl(tool_result_records, tool_results_path)

    summary = {
        "candidates_input": str(candidates_path),
        "query_catalog": str(query_catalog_path),
        "candidates_processed": len(results),
        "agent_results": str(results_path),
        "reports_dir": str(reports_dir),
        "status_counts": _status_counts(results),
        "llm_mode": normalized_llm_mode,
        "program_trace": str(program_trace_path),
        "tool_results": str(tool_results_path),
        "candidate_ledgers": str(ledgers_dir),
        "agent_events": str(output_dir / Path(event_log)),
    }
    (output_dir / "agent_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _reason_candidate(
    *,
    candidate: dict[str, Any],
    candidate_index: int,
    query_catalog: dict[str, dict[str, str | None]],
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
    llm_provider: LLMProvider,
    max_rounds: int,
    prompt_dir: Path | str | None,
    schema_retries: int,
    event_logger: JsonlEventLogger,
    tool_executor: EvidenceToolExecutor,
    accession_enricher: AccessionEnricher,
    accession_cache_dir: str | None,
    candidate_cohort: list[dict[str, Any]],
) -> dict[str, Any]:
    examples: list[dict[str, Any]] = []
    uncertainties: list[str] = []
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

    query_id = str(candidate.get("query_id") or "").strip()
    query_record = query_catalog.get(query_id)
    if query_record is None:
        raise ValueError(f"query_catalog does not contain query_id={query_id!r} for candidate {_candidate_slug(candidate)}")

    representative_neighbor_id = _first_neighbor_id(examples)
    sequence_evidence = _sequence_evidence(
        protein_id=representative_neighbor_id,
        sequences=sequences,
        include_sequences=include_sequences,
        flank_bp=flank_bp,
        sequence_max_bases=sequence_max_bases,
        uncertainties=uncertainties,
    )
    seed_summary = SeedSummary.from_query_and_examples(query_record=query_record, examples=examples).to_dict()
    candidate_neighbor_summary = _candidate_neighbor_summary(examples, representative_neighbor_id)
    checklist = _falsification_checklist(candidate, examples, sequence_evidence)

    runtime_result = run_research_runtime(
        candidate_index=candidate_index,
        candidate_slug=_candidate_slug(candidate),
        runtime_inputs={
            "candidate_summary": _candidate_summary(candidate),
            "seed_summary": seed_summary,
            "candidate_neighbor_summary": candidate_neighbor_summary,
            "occurrence_bundle": {
                "examples": examples,
                "sequence_evidence": sequence_evidence,
                "candidate_cohort": candidate_cohort,
            },
        },
        provider=llm_provider,
        tool_executor=tool_executor,
        max_rounds=max_rounds,
        prompt_dir=prompt_dir,
        schema_retries=schema_retries,
        accession_enricher=accession_enricher,
        accession_cache_dir=accession_cache_dir,
        event_logger=event_logger,
    )

    result: dict[str, Any] = {
        "candidate": _candidate_summary(candidate),
        "seed_summary": seed_summary,
        "candidate_neighbor_summary": candidate_neighbor_summary,
        "examples": examples,
        "sequence_evidence": sequence_evidence,
        "falsification_checklist": checklist,
        "reasoning": runtime_result.reasoning,
        "uncertainties": uncertainties + _ledger_uncertainties(runtime_result.ledger),
        "ledger": runtime_result.ledger,
    }
    ledger_path = ledgers_dir / f"{candidate_index:04d}-{_candidate_slug(candidate)}.json"
    ledger_path.write_text(json.dumps(runtime_result.ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["ledger_path"] = str(ledger_path)
    result["_program_trace_records"] = runtime_result.role_calls
    result["_tool_result_records"] = runtime_result.ledger.get("tool_runs", [])
    report_path = reports_dir / f"{candidate_index:04d}-{_candidate_slug(candidate)}.md"
    result["report_path"] = str(report_path)
    report_path.write_text(render_agent_report(result), encoding="utf-8")
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


def _candidate_neighbor_summary(examples: list[dict[str, Any]], representative_neighbor_id: str | None) -> dict[str, Any]:
    fields = ("product", "gene_name", "pfam", "interpro", "kegg", "cog_id", "cog_category")
    summary: dict[str, Any] = {"protein_id": representative_neighbor_id}
    for field in fields:
        for example in examples:
            neighbor = example.get("neighbor_protein") or {}
            value = neighbor.get(field)
            if value:
                summary[field] = value
                break
        else:
            summary[field] = None
    return summary


def _candidate_cohort_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": candidate.get("query_id"),
        "cluster_30": candidate.get("cluster_30"),
        "presence_contexts": candidate.get("presence_contexts"),
        "protein_length": candidate.get("protein_length"),
    }


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


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = result["reasoning"]["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _candidate_slug(candidate: dict[str, Any]) -> str:
    raw = f"{candidate.get('query_id', 'query')}-{candidate.get('cluster_30', 'cluster')}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-") or "candidate"


def _ledger_uncertainties(ledger: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    notebook = ledger.get("notebook") or {}
    for bridge in notebook.get("failed_bridges", []):
        reason = str(bridge.get("reason") or "").strip()
        if reason:
            notes.append(reason)
    return notes


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
