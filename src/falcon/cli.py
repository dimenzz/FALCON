from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any
from datetime import datetime, timezone
import json
import sqlite3

import typer
import yaml

from falcon.config import load_config
from falcon.context.extractor import extract_context
from falcon.cohort.builder import build_context_cohort
from falcon.colocation.background import build_background_abundance
from falcon.colocation.scoring import score_colocation
from falcon.agent.reasoning import reason_candidates
from falcon.data.manifests import inspect_manifest
from falcon.data.proteins import ProteinNotFoundError
from falcon.data.sequences import SequenceRepository
from falcon.data.sqlite import inspect_sqlite
from falcon.homology.search import (
    parse_hits_tsv,
    run_mmseqs_search,
    target_db_for_level,
    write_hits_jsonl,
)
from falcon.homology.seeds import load_seed_records, write_seeds_jsonl
from falcon.models import WindowMode
from falcon.tools.runner import ExternalCommandError


app = typer.Typer(no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
homology_app = typer.Typer(no_args_is_help=True)
cohort_app = typer.Typer(no_args_is_help=True)
background_app = typer.Typer(no_args_is_help=True)
colocation_app = typer.Typer(no_args_is_help=True)
sequence_app = typer.Typer(no_args_is_help=True)
agent_app = typer.Typer(no_args_is_help=True)
app.add_typer(config_app, name="config")
app.add_typer(homology_app, name="homology")
app.add_typer(cohort_app, name="cohort")
app.add_typer(background_app, name="background")
app.add_typer(colocation_app, name="colocation")
app.add_typer(sequence_app, name="sequence")
app.add_typer(agent_app, name="agent")


class OutputFormat(str, Enum):
    JSON = "json"
    YAML = "yaml"


def _path_value(value: Path | None) -> str | None:
    return str(value) if value is not None else None


def _compact_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(value, dict):
            nested = _compact_mapping(value)
            if nested:
                compact[key] = nested
        elif value is not None:
            compact[key] = value
    return compact


def _build_overrides(
    *,
    proteins_db: Path | None = None,
    clusters_db: Path | None = None,
    genome_manifest: Path | None = None,
    protein_manifest: Path | None = None,
    mmseqs_db_root: Path | None = None,
    mmseqs: Path | None = None,
    interproscan: Path | None = None,
    interproscan_threads: int | None = None,
    window_mode: WindowMode | None = None,
    upstream: int | None = None,
    downstream: int | None = None,
    bp_upstream: int | None = None,
    bp_downstream: int | None = None,
    include_clusters: bool | None = None,
    search_level: int | None = None,
    statistics_neighbor_level: int | None = None,
    expand_30_contexts: bool | None = None,
    sensitivity: float | None = None,
    evalue: float | None = None,
    max_seqs: int | None = None,
    threads: int | None = None,
    min_contexts: int | None = None,
    min_presence_rate: float | None = None,
    min_fold_enrichment: float | None = None,
    max_qvalue: float | None = None,
    max_examples: int | None = None,
    no_filtering: bool | None = None,
    sequence_max_bases: int | None = None,
    max_candidates: int | None = None,
    agent_max_examples: int | None = None,
    include_sequences: bool | None = None,
    flank_bp: int | None = None,
) -> dict[str, Any]:
    return _compact_mapping(
        {
            "data": {
                "proteins_db": _path_value(proteins_db),
                "clusters_db": _path_value(clusters_db),
                "genome_manifest": _path_value(genome_manifest),
                "protein_manifest": _path_value(protein_manifest),
                "mmseqs_db_root": _path_value(mmseqs_db_root),
            },
            "tools": {
                "mmseqs": _path_value(mmseqs),
                "interproscan": _path_value(interproscan),
                "interproscan_threads": interproscan_threads,
            },
            "context": {
                "window_mode": window_mode.value if window_mode is not None else None,
                "upstream": upstream,
                "downstream": downstream,
                "bp_upstream": bp_upstream,
                "bp_downstream": bp_downstream,
                "include_clusters": include_clusters,
            },
            "homology": {
                "search_level": search_level,
                "sensitivity": sensitivity,
                "evalue": evalue,
                "max_seqs": max_seqs,
                "threads": threads,
            },
            "clusters": {
                "search_level": search_level,
                "statistics_neighbor_level": statistics_neighbor_level,
                "expand_30_contexts": expand_30_contexts,
            },
            "colocation": {
                "min_contexts": min_contexts,
                "min_presence_rate": min_presence_rate,
                "min_fold_enrichment": min_fold_enrichment,
                "max_qvalue": max_qvalue,
                "max_examples": max_examples,
                "no_filtering": no_filtering,
            },
            "sequence": {
                "max_bases": sequence_max_bases,
            },
            "agent": {
                "max_candidates": max_candidates,
                "max_examples": agent_max_examples,
                "include_sequences": include_sequences,
                "flank_bp": flank_bp,
            },
        }
    )


def _emit(payload: Any, output: OutputFormat = OutputFormat.JSON) -> None:
    if output is OutputFormat.YAML:
        typer.echo(yaml.safe_dump(payload, sort_keys=True))
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@config_app.command("show")
def show_config(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    clusters_db: Annotated[Path | None, typer.Option("--clusters-db")] = None,
    genome_manifest: Annotated[Path | None, typer.Option("--genome-manifest")] = None,
    protein_manifest: Annotated[Path | None, typer.Option("--protein-manifest")] = None,
    mmseqs_db_root: Annotated[Path | None, typer.Option("--mmseqs-db-root")] = None,
    mmseqs: Annotated[Path | None, typer.Option("--mmseqs")] = None,
    interproscan: Annotated[Path | None, typer.Option("--interproscan")] = None,
    interproscan_threads: Annotated[int | None, typer.Option("--interproscan-threads")] = None,
    window_mode: Annotated[WindowMode | None, typer.Option("--window-mode")] = None,
    upstream: Annotated[int | None, typer.Option("--upstream")] = None,
    downstream: Annotated[int | None, typer.Option("--downstream")] = None,
    bp_upstream: Annotated[int | None, typer.Option("--bp-upstream")] = None,
    bp_downstream: Annotated[int | None, typer.Option("--bp-downstream")] = None,
    search_level: Annotated[int | None, typer.Option("--search-level")] = None,
    statistics_neighbor_level: Annotated[int | None, typer.Option("--statistics-neighbor-level")] = None,
    expand_30_contexts: Annotated[bool | None, typer.Option("--expand-30-contexts/--no-expand-30-contexts")] = None,
    sensitivity: Annotated[float | None, typer.Option("--sensitivity", "-s")] = None,
    evalue: Annotated[float | None, typer.Option("--evalue", "-e")] = None,
    max_seqs: Annotated[int | None, typer.Option("--max-seqs")] = None,
    threads: Annotated[int | None, typer.Option("--threads")] = None,
    min_contexts: Annotated[int | None, typer.Option("--min-contexts")] = None,
    min_presence_rate: Annotated[float | None, typer.Option("--min-presence-rate")] = None,
    min_fold_enrichment: Annotated[float | None, typer.Option("--min-fold-enrichment")] = None,
    max_qvalue: Annotated[float | None, typer.Option("--max-qvalue")] = None,
    max_examples: Annotated[int | None, typer.Option("--max-examples")] = None,
    no_filtering: Annotated[bool | None, typer.Option("--no-filtering/--filtering")] = None,
    sequence_max_bases: Annotated[int | None, typer.Option("--sequence-max-bases")] = None,
    max_candidates: Annotated[int | None, typer.Option("--max-candidates")] = None,
    agent_max_examples: Annotated[int | None, typer.Option("--agent-max-examples")] = None,
    include_sequences: Annotated[bool | None, typer.Option("--include-sequences/--no-include-sequences")] = None,
    flank_bp: Annotated[int | None, typer.Option("--flank-bp")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            clusters_db=clusters_db,
            genome_manifest=genome_manifest,
            protein_manifest=protein_manifest,
            mmseqs_db_root=mmseqs_db_root,
            mmseqs=mmseqs,
            interproscan=interproscan,
            interproscan_threads=interproscan_threads,
            window_mode=window_mode,
            upstream=upstream,
            downstream=downstream,
            bp_upstream=bp_upstream,
            bp_downstream=bp_downstream,
            search_level=search_level,
            statistics_neighbor_level=statistics_neighbor_level,
            expand_30_contexts=expand_30_contexts,
            sensitivity=sensitivity,
            evalue=evalue,
            max_seqs=max_seqs,
            threads=threads,
            min_contexts=min_contexts,
            min_presence_rate=min_presence_rate,
            min_fold_enrichment=min_fold_enrichment,
            max_qvalue=max_qvalue,
            max_examples=max_examples,
            no_filtering=no_filtering,
            sequence_max_bases=sequence_max_bases,
            max_candidates=max_candidates,
            agent_max_examples=agent_max_examples,
            include_sequences=include_sequences,
            flank_bp=flank_bp,
        ),
    )
    _emit(config, output)


@app.command("inspect")
def inspect(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    clusters_db: Annotated[Path | None, typer.Option("--clusters-db")] = None,
    genome_manifest: Annotated[Path | None, typer.Option("--genome-manifest")] = None,
    protein_manifest: Annotated[Path | None, typer.Option("--protein-manifest")] = None,
    mmseqs_db_root: Annotated[Path | None, typer.Option("--mmseqs-db-root")] = None,
    mmseqs: Annotated[Path | None, typer.Option("--mmseqs")] = None,
    interproscan: Annotated[Path | None, typer.Option("--interproscan")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            clusters_db=clusters_db,
            genome_manifest=genome_manifest,
            protein_manifest=protein_manifest,
            mmseqs_db_root=mmseqs_db_root,
            mmseqs=mmseqs,
            interproscan=interproscan,
        ),
    )

    mmseqs_root = Path(config["data"]["mmseqs_db_root"])
    mmseqs_path = Path(config["tools"]["mmseqs"])
    interproscan_path = Path(config["tools"]["interproscan"])
    payload = {
        "sqlite": {
            "proteins_db": inspect_sqlite(config["data"]["proteins_db"], ["proteins"]),
            "clusters_db": inspect_sqlite(config["data"]["clusters_db"], ["clusters"]),
        },
        "manifests": {
            "genome_manifest": inspect_manifest(config["data"]["genome_manifest"]),
            "protein_manifest": inspect_manifest(config["data"]["protein_manifest"]),
        },
        "mmseqs_db_root": {
            "path": str(mmseqs_root),
            "exists": mmseqs_root.exists(),
            "ok": mmseqs_root.exists() and mmseqs_root.is_dir(),
        },
        "tools": {
            "mmseqs": _inspect_executable(mmseqs_path),
            "interproscan": _inspect_executable(interproscan_path),
        },
    }
    _emit(payload, output)


@app.command("context")
def context(
    protein_id: Annotated[str, typer.Argument()],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    clusters_db: Annotated[Path | None, typer.Option("--clusters-db")] = None,
    window_mode: Annotated[WindowMode | None, typer.Option("--window-mode")] = None,
    upstream: Annotated[int | None, typer.Option("--upstream")] = None,
    downstream: Annotated[int | None, typer.Option("--downstream")] = None,
    bp_upstream: Annotated[int | None, typer.Option("--bp-upstream")] = None,
    bp_downstream: Annotated[int | None, typer.Option("--bp-downstream")] = None,
    include_clusters: Annotated[bool | None, typer.Option("--include-clusters/--no-include-clusters")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            clusters_db=clusters_db,
            window_mode=window_mode,
            upstream=upstream,
            downstream=downstream,
            bp_upstream=bp_upstream,
            bp_downstream=bp_downstream,
            include_clusters=include_clusters,
        ),
    )

    try:
        result = extract_context(
            protein_id=protein_id,
            proteins_db=config["data"]["proteins_db"],
            clusters_db=config["data"].get("clusters_db"),
            window_mode=config["context"]["window_mode"],
            upstream=int(config["context"]["upstream"]),
            downstream=int(config["context"]["downstream"]),
            bp_upstream=int(config["context"]["bp_upstream"]),
            bp_downstream=int(config["context"]["bp_downstream"]),
            include_clusters=bool(config["context"]["include_clusters"]),
        )
    except ProteinNotFoundError as exc:
        typer.echo(f"Protein not found: {exc.protein_id}", err=True)
        raise typer.Exit(1) from exc
    except (sqlite3.Error, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    _emit(result, output)


@homology_app.command("search")
def homology_search(
    query: Annotated[Path, typer.Option("--query")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    seed_metadata: Annotated[Path | None, typer.Option("--seed-metadata")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    search_level: Annotated[int | None, typer.Option("--search-level")] = None,
    sensitivity: Annotated[float | None, typer.Option("--sensitivity", "-s")] = None,
    evalue: Annotated[float | None, typer.Option("--evalue", "-e")] = None,
    max_seqs: Annotated[int | None, typer.Option("--max-seqs")] = None,
    threads: Annotated[int | None, typer.Option("--threads")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            search_level=search_level,
            sensitivity=sensitivity,
            evalue=evalue,
            max_seqs=max_seqs,
            threads=threads,
        ),
    )
    run_dir = out_dir or _default_run_dir(config, "homology")
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        seeds, warnings = load_seed_records(query, seed_metadata)
        raw_hits = run_dir / "raw_hits.tsv"
        tool_trace = run_mmseqs_search(
            mmseqs_path=config["tools"]["mmseqs"],
            query_fasta=query,
            target_db=target_db_for_level(
                config["data"]["mmseqs_db_root"],
                int(config["homology"]["search_level"]),
            ),
            output_tsv=raw_hits,
            tmp_dir=Path(config["runtime"]["cache_dir"]) / "mmseqs_tmp",
            sensitivity=float(config["homology"]["sensitivity"]),
            evalue=float(config["homology"]["evalue"]),
            max_seqs=int(config["homology"]["max_seqs"]),
            threads=int(config["homology"]["threads"]),
            format_fields=list(config["homology"]["format_fields"]),
            log_dir=Path(config["runtime"]["log_dir"]),
        )
        hits = parse_hits_tsv(raw_hits, int(config["homology"]["search_level"]))
    except (OSError, ValueError, sqlite3.Error, ExternalCommandError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    write_seeds_jsonl(seeds, run_dir / "seeds.jsonl")
    write_hits_jsonl(hits, run_dir / "hits.jsonl")
    summary = {
        "query": str(query),
        "seed_metadata": str(seed_metadata) if seed_metadata is not None else None,
        "seeds": len(seeds),
        "hits": len(hits),
        "search_level": int(config["homology"]["search_level"]),
        "threads": int(config["homology"]["threads"]),
        "out_dir": str(run_dir),
        "raw_hits": str(raw_hits),
        "hits_jsonl": str(run_dir / "hits.jsonl"),
        "seeds_jsonl": str(run_dir / "seeds.jsonl"),
        "tool_trace": tool_trace,
        "warnings": warnings,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _emit(summary, output)


@cohort_app.command("build")
def cohort_build(
    hits: Annotated[Path, typer.Option("--hits")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    search_level: Annotated[int | None, typer.Option("--search-level")] = None,
    expand_30_contexts: Annotated[bool | None, typer.Option("--expand-30-contexts/--no-expand-30-contexts")] = None,
    window_mode: Annotated[WindowMode | None, typer.Option("--window-mode")] = None,
    upstream: Annotated[int | None, typer.Option("--upstream")] = None,
    downstream: Annotated[int | None, typer.Option("--downstream")] = None,
    bp_upstream: Annotated[int | None, typer.Option("--bp-upstream")] = None,
    bp_downstream: Annotated[int | None, typer.Option("--bp-downstream")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            search_level=search_level,
            expand_30_contexts=expand_30_contexts,
            window_mode=window_mode,
            upstream=upstream,
            downstream=downstream,
            bp_upstream=bp_upstream,
            bp_downstream=bp_downstream,
        ),
    )
    run_dir = out_dir or hits.parent
    try:
        summary = build_context_cohort(
            hits_path=hits,
            proteins_db=config["data"]["proteins_db"],
            clusters_db=config["data"]["clusters_db"],
            out_dir=run_dir,
            search_level=search_level,
            expand_30_contexts=bool(config["clusters"]["expand_30_contexts"]),
            window_mode=config["context"]["window_mode"],
            upstream=int(config["context"]["upstream"]),
            downstream=int(config["context"]["downstream"]),
            bp_upstream=int(config["context"]["bp_upstream"]),
            bp_downstream=int(config["context"]["bp_downstream"]),
        )
    except (OSError, ValueError, ProteinNotFoundError, sqlite3.Error) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(summary, output)


@background_app.command("build")
def background_build(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    clusters_db: Annotated[Path | None, typer.Option("--clusters-db")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(clusters_db=clusters_db),
    )
    output_dir = out_dir or Path(config["background"]["output_dir"])
    try:
        summary = build_background_abundance(
            clusters_db=config["data"]["clusters_db"],
            out_dir=output_dir,
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(summary, output)


@colocation_app.command("score")
def colocation_score(
    cohort_contexts: Annotated[Path, typer.Option("--cohort-contexts")],
    background: Annotated[Path, typer.Option("--background")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    min_contexts: Annotated[int | None, typer.Option("--min-contexts")] = None,
    min_presence_rate: Annotated[float | None, typer.Option("--min-presence-rate")] = None,
    min_fold_enrichment: Annotated[float | None, typer.Option("--min-fold-enrichment")] = None,
    max_qvalue: Annotated[float | None, typer.Option("--max-qvalue")] = None,
    max_examples: Annotated[int | None, typer.Option("--max-examples")] = None,
    no_filtering: Annotated[bool | None, typer.Option("--no-filtering/--filtering")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            min_contexts=min_contexts,
            min_presence_rate=min_presence_rate,
            min_fold_enrichment=min_fold_enrichment,
            max_qvalue=max_qvalue,
            max_examples=max_examples,
            no_filtering=no_filtering,
        ),
    )
    output_dir = out_dir or cohort_contexts.parent
    try:
        summary = score_colocation(
            cohort_contexts=cohort_contexts,
            background=background,
            out_dir=output_dir,
            min_contexts=int(config["colocation"]["min_contexts"]),
            min_presence_rate=float(config["colocation"]["min_presence_rate"]),
            min_fold_enrichment=float(config["colocation"]["min_fold_enrichment"]),
            max_qvalue=float(config["colocation"]["max_qvalue"]),
            max_examples=int(config["colocation"]["max_examples"]),
            no_filtering=bool(config["colocation"]["no_filtering"]),
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(summary, output)


@sequence_app.command("protein")
def sequence_protein(
    protein_id: Annotated[str, typer.Option("--protein-id")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    genome_manifest: Annotated[Path | None, typer.Option("--genome-manifest")] = None,
    protein_manifest: Annotated[Path | None, typer.Option("--protein-manifest")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            genome_manifest=genome_manifest,
            protein_manifest=protein_manifest,
        ),
    )
    try:
        with SequenceRepository(
            proteins_db=config["data"]["proteins_db"],
            protein_manifest=config["data"]["protein_manifest"],
            genome_manifest=config["data"]["genome_manifest"],
        ) as sequences:
            result = sequences.get_protein_sequence(protein_id)
    except (OSError, KeyError, ValueError, sqlite3.Error) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(result, output)


@sequence_app.command("dna")
def sequence_dna(
    protein_id: Annotated[str, typer.Option("--protein-id")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    genome_manifest: Annotated[Path | None, typer.Option("--genome-manifest")] = None,
    protein_manifest: Annotated[Path | None, typer.Option("--protein-manifest")] = None,
    flank_bp: Annotated[int, typer.Option("--flank-bp")] = 0,
    max_bases: Annotated[int | None, typer.Option("--max-bases")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            genome_manifest=genome_manifest,
            protein_manifest=protein_manifest,
            sequence_max_bases=max_bases,
        ),
    )
    try:
        with SequenceRepository(
            proteins_db=config["data"]["proteins_db"],
            protein_manifest=config["data"]["protein_manifest"],
            genome_manifest=config["data"]["genome_manifest"],
        ) as sequences:
            result = sequences.get_dna_for_protein(
                protein_id,
                flank_bp=flank_bp,
                max_bases=int(config["sequence"]["max_bases"]),
            )
    except (OSError, KeyError, ValueError, sqlite3.Error) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(result, output)


@agent_app.command("reason")
def agent_reason(
    candidates: Annotated[Path, typer.Option("--candidates")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    proteins_db: Annotated[Path | None, typer.Option("--proteins-db")] = None,
    clusters_db: Annotated[Path | None, typer.Option("--clusters-db")] = None,
    genome_manifest: Annotated[Path | None, typer.Option("--genome-manifest")] = None,
    protein_manifest: Annotated[Path | None, typer.Option("--protein-manifest")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    max_candidates: Annotated[int | None, typer.Option("--max-candidates")] = None,
    max_examples: Annotated[int | None, typer.Option("--max-examples")] = None,
    include_sequences: Annotated[bool | None, typer.Option("--include-sequences/--no-include-sequences")] = None,
    flank_bp: Annotated[int | None, typer.Option("--flank-bp")] = None,
    sequence_max_bases: Annotated[int | None, typer.Option("--sequence-max-bases")] = None,
    output: Annotated[OutputFormat, typer.Option("--output")] = OutputFormat.JSON,
) -> None:
    config = load_config(
        config_path,
        _build_overrides(
            proteins_db=proteins_db,
            clusters_db=clusters_db,
            genome_manifest=genome_manifest,
            protein_manifest=protein_manifest,
            max_candidates=max_candidates,
            agent_max_examples=max_examples,
            include_sequences=include_sequences,
            flank_bp=flank_bp,
            sequence_max_bases=sequence_max_bases,
        ),
    )
    output_dir = out_dir or _default_run_dir(config, "agent")
    try:
        summary = reason_candidates(
            candidates_path=candidates,
            proteins_db=config["data"]["proteins_db"],
            clusters_db=config["data"]["clusters_db"],
            protein_manifest=config["data"]["protein_manifest"],
            genome_manifest=config["data"]["genome_manifest"],
            out_dir=output_dir,
            max_candidates=int(config["agent"]["max_candidates"]),
            max_examples=int(config["agent"]["max_examples"]),
            include_sequences=bool(config["agent"]["include_sequences"]),
            flank_bp=int(config["agent"]["flank_bp"]),
            sequence_max_bases=int(config["sequence"]["max_bases"]),
        )
    except (OSError, KeyError, ValueError, sqlite3.Error) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _emit(summary, output)


def _inspect_executable(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "executable": path.exists() and path.is_file() and path.stat().st_mode & 0o111 != 0,
        "ok": path.exists() and path.is_file(),
    }


def _default_run_dir(config: dict[str, Any], prefix: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(config["runtime"].get("runs_dir", "runs")) / f"{prefix}-{timestamp}"
