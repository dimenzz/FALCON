from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import json
import math

from scipy.stats import fisher_exact

from falcon.homology.search import write_jsonl


def score_colocation(
    *,
    cohort_contexts: Path | str,
    background: Path | str,
    out_dir: Path | str,
    min_contexts: int,
    min_presence_rate: float,
    min_fold_enrichment: float,
    max_qvalue: float,
    max_examples: int,
    no_filtering: bool,
    max_candidates: int | None = None,
) -> dict[str, Any]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    background_payload = _load_background(background)
    bg_counts = {
        row["cluster_30"]: int(row["count_90_representatives"])
        for row in background_payload["clusters"]
    }
    bg_probs = {
        row["cluster_30"]: float(row["background_probability"])
        for row in background_payload["clusters"]
    }
    background_total = int(background_payload["total_90_representatives"])

    query_contexts: dict[str, set[str]] = defaultdict(set)
    query_cluster_contexts: dict[tuple[str, str], set[str]] = defaultdict(set)
    query_cluster_copy_count: dict[tuple[str, str], int] = defaultdict(int)
    query_cluster_examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for record in _read_jsonl(cohort_contexts):
        context_id = str(record["protein_id"])
        query_ids = sorted({str(hit["query_id"]) for hit in record.get("supporting_hits", [])})
        target_cluster = _target_cluster(record)
        seen_in_context: set[str] = set()
        for item in record["context"]["context"]:
            if item.get("is_target"):
                continue
            cluster_30 = item.get("clusters", {}).get("30")
            if not cluster_30 or cluster_30 == target_cluster:
                continue
            for query_id in query_ids:
                query_contexts[query_id].add(context_id)
                query_cluster_copy_count[(query_id, cluster_30)] += 1
                if len(query_cluster_examples[(query_id, cluster_30)]) < max_examples:
                    query_cluster_examples[(query_id, cluster_30)].append(
                        {
                            "context_protein_id": context_id,
                            "neighbor_protein": item["protein"],
                            "relative_index": item.get("relative_index"),
                            "supporting_hits": record.get("supporting_hits", []),
                        }
                    )
            seen_in_context.add(cluster_30)

        for query_id in query_ids:
            query_contexts[query_id].add(context_id)
            for cluster_30 in seen_in_context:
                query_cluster_contexts[(query_id, cluster_30)].add(context_id)

    stats = []
    for (query_id, cluster_30), contexts in sorted(query_cluster_contexts.items()):
        observed = len(contexts)
        total_contexts = len(query_contexts[query_id])
        background_count = bg_counts.get(cluster_30, 0)
        background_probability = bg_probs.get(cluster_30, 0.0)
        presence_rate = observed / total_contexts if total_contexts else 0.0
        fold_enrichment = _fold_enrichment(presence_rate, background_probability)
        _, p_value = fisher_exact(
            [
                [observed, max(total_contexts - observed, 0)],
                [background_count, max(background_total - background_count, 0)],
            ],
            alternative="greater",
        )
        stats.append(
            {
                "query_id": query_id,
                "cluster_30": cluster_30,
                "query_contexts": total_contexts,
                "presence_contexts": observed,
                "copy_count": query_cluster_copy_count[(query_id, cluster_30)],
                "background_count": background_count,
                "background_total": background_total,
                "background_probability": background_probability,
                "presence_rate": presence_rate,
                "fold_enrichment": fold_enrichment,
                "p_value": p_value,
                "examples": query_cluster_examples[(query_id, cluster_30)][:max_examples],
            }
        )

    _add_bh_q_values(stats)
    stats.sort(key=lambda row: (row["q_value"], -row["fold_enrichment"], row["query_id"], row["cluster_30"]))
    filter_diagnostics = _filter_diagnostics(
        stats,
        min_contexts=min_contexts,
        min_presence_rate=min_presence_rate,
        min_fold_enrichment=min_fold_enrichment,
        max_qvalue=max_qvalue,
    )
    candidates_before_limit = [
        row
        for row in stats
        if no_filtering
        or (
            row["presence_contexts"] >= min_contexts
            and row["presence_rate"] >= min_presence_rate
            and row["fold_enrichment"] >= min_fold_enrichment
            and row["q_value"] <= max_qvalue
        )
    ]
    candidates_before_limit.sort(key=_candidate_sort_key)
    candidates = _limit_candidates(candidates_before_limit, max_candidates)

    stats_path = output_dir / "colocation_stats.jsonl"
    candidates_path = output_dir / "candidate_neighbors.jsonl"
    candidates_tsv_path = output_dir / "candidate_neighbors.tsv"
    write_jsonl(stats, stats_path)
    write_jsonl(candidates, candidates_path)
    _write_candidates_tsv(candidates, candidates_tsv_path)
    summary = {
        "query_count": len(query_contexts),
        "stat_rows": len(stats),
        "candidates": len(candidates),
        "candidates_before_limit": len(candidates_before_limit),
        "colocation_stats": str(stats_path),
        "candidate_neighbors": str(candidates_path),
        "candidate_neighbors_tsv": str(candidates_tsv_path),
        "filter_diagnostics": filter_diagnostics,
        "max_candidates": max_candidates,
        "no_filtering": no_filtering,
    }
    (output_dir / "colocation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _load_background(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _target_cluster(record: dict[str, Any]) -> str | None:
    return (
        record.get("representative_30")
        or record.get("context", {}).get("target", {}).get("clusters", {}).get("30")
    )


def _fold_enrichment(presence_rate: float, background_probability: float) -> float:
    if background_probability == 0:
        return math.inf if presence_rate > 0 else 0.0
    return presence_rate / background_probability


def _add_bh_q_values(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["p_value"], reverse=True)
    previous = 1.0
    total = len(rows)
    for reverse_rank, (original_index, row) in enumerate(ordered, start=1):
        rank = total - reverse_rank + 1
        q_value = min(previous, row["p_value"] * total / rank)
        previous = q_value
        rows[original_index]["q_value"] = min(q_value, 1.0)


def _filter_diagnostics(
    rows: list[dict[str, Any]],
    *,
    min_contexts: int,
    min_presence_rate: float,
    min_fold_enrichment: float,
    max_qvalue: float,
) -> dict[str, Any]:
    return {
        "total": len(rows),
        "presence_contexts": sum(1 for row in rows if row["presence_contexts"] >= min_contexts),
        "presence_rate": sum(1 for row in rows if row["presence_rate"] >= min_presence_rate),
        "fold_enrichment": sum(1 for row in rows if row["fold_enrichment"] >= min_fold_enrichment),
        "q_value": sum(1 for row in rows if row["q_value"] <= max_qvalue),
        "combined_before_limit": sum(
            1
            for row in rows
            if row["presence_contexts"] >= min_contexts
            and row["presence_rate"] >= min_presence_rate
            and row["fold_enrichment"] >= min_fold_enrichment
            and row["q_value"] <= max_qvalue
        ),
        "thresholds": {
            "min_contexts": min_contexts,
            "min_presence_rate": min_presence_rate,
            "min_fold_enrichment": min_fold_enrichment,
            "max_qvalue": max_qvalue,
        },
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -row["presence_contexts"],
        row["q_value"],
        -row["fold_enrichment"],
        row["query_id"],
        row["cluster_30"],
    )


def _limit_candidates(
    candidates: list[dict[str, Any]],
    max_candidates: int | None,
) -> list[dict[str, Any]]:
    if max_candidates is None or int(max_candidates) <= 0:
        return candidates
    return candidates[: int(max_candidates)]


def _write_candidates_tsv(candidates: list[dict[str, Any]], path: Path | str) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(
            "query_id\tcluster_30\tpresence_contexts\tquery_contexts\tcopy_count\t"
            "presence_rate\tbackground_probability\tfold_enrichment\tp_value\tq_value\t"
            "example_neighbor_ids\texample_products\n"
        )
        for row in candidates:
            example_neighbor_ids, example_products = _example_summaries(row)
            handle.write(
                f"{row['query_id']}\t{row['cluster_30']}\t{row['presence_contexts']}\t"
                f"{row['query_contexts']}\t{row['copy_count']}\t{row['presence_rate']}\t"
                f"{row['background_probability']}\t{row['fold_enrichment']}\t"
                f"{row['p_value']}\t{row['q_value']}\t"
                f"{example_neighbor_ids}\t{example_products}\n"
            )


def _example_summaries(row: dict[str, Any]) -> tuple[str, str]:
    ids = []
    products = []
    for example in row.get("examples", []):
        protein = example.get("neighbor_protein", {})
        if protein.get("protein_id"):
            ids.append(str(protein["protein_id"]))
        if protein.get("product"):
            products.append(str(protein["product"]).replace("\t", " "))
    return ";".join(ids), ";".join(products)
