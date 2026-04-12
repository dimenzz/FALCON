from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import re

from falcon.context.extractor import extract_context
from falcon.data.clusters import ClusterRepository
from falcon.data.proteins import ProteinNotFoundError, ProteinRepository
from falcon.data.sequences import SequenceRepository
from falcon.homology.search import write_jsonl
from falcon.reporting.markdown import render_agent_report


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
) -> dict[str, Any]:
    output_dir = Path(out_dir)
    reports_dir = output_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    candidates = _read_jsonl(candidates_path)
    if max_candidates is not None:
        candidates = candidates[: int(max_candidates)]

    results = []
    with ProteinRepository(proteins_db) as proteins, ClusterRepository(clusters_db) as clusters, SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        for index, candidate in enumerate(candidates, start=1):
            result = _reason_candidate(
                candidate=candidate,
                candidate_index=index,
                proteins=proteins,
                clusters=clusters,
                sequences=sequences,
                proteins_db=proteins_db,
                clusters_db=clusters_db,
                reports_dir=reports_dir,
                max_examples=max_examples,
                include_sequences=include_sequences,
                flank_bp=flank_bp,
                sequence_max_bases=sequence_max_bases,
            )
            results.append(result)

    results_path = output_dir / "agent_results.jsonl"
    write_jsonl(results, results_path)
    summary = {
        "candidates_input": str(candidates_path),
        "candidates_processed": len(results),
        "agent_results": str(results_path),
        "reports_dir": str(reports_dir),
        "status_counts": _status_counts(results),
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
    proteins: ProteinRepository,
    clusters: ClusterRepository,
    sequences: SequenceRepository,
    proteins_db: Path | str,
    clusters_db: Path | str,
    reports_dir: Path,
    max_examples: int,
    include_sequences: bool,
    flank_bp: int,
    sequence_max_bases: int,
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


def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = result["reasoning"]["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _candidate_slug(candidate: dict[str, Any]) -> str:
    raw = f"{candidate.get('query_id', 'query')}-{candidate.get('cluster_30', 'cluster')}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-") or "candidate"
