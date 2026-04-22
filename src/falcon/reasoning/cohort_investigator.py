from __future__ import annotations

from statistics import mean
from typing import Any


def compare_candidate_lengths(
    *,
    with_pattern: list[dict[str, Any]],
    without_pattern: list[dict[str, Any]],
) -> dict[str, Any]:
    with_lengths = [float(item["protein_length"]) for item in with_pattern if item.get("protein_length") is not None]
    without_lengths = [
        float(item["protein_length"])
        for item in without_pattern
        if item.get("protein_length") is not None
    ]
    if not with_lengths or not without_lengths:
        return {"status": "unresolved", "reason": "missing length observations"}
    with_mean = mean(with_lengths)
    without_mean = mean(without_lengths)
    return {
        "status": "ok",
        "with_pattern_mean_length": with_mean,
        "without_pattern_mean_length": without_mean,
        "delta_mean_length": with_mean - without_mean,
    }


def compare_neighbor_covariation(*, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    support_totals: dict[str, int] = {}
    for candidate in candidates:
        cluster = str(candidate.get("cluster_30") or "").strip()
        if not cluster:
            continue
        counts[cluster] = counts.get(cluster, 0) + 1
        support_totals[cluster] = support_totals.get(cluster, 0) + int(candidate.get("presence_contexts") or 0)
    ranked = sorted(
        (
            {
                "cluster_30": cluster,
                "candidate_count": counts[cluster],
                "support_total": support_totals[cluster],
            }
            for cluster in counts
        ),
        key=lambda item: (-item["candidate_count"], -item["support_total"], item["cluster_30"]),
    )
    return {"status": "ok", "ranked_clusters": ranked}


def summarize_cohort_patterns(
    *,
    query_id: str,
    program_type: str,
    length_shift: dict[str, Any],
    covariation: dict[str, Any],
) -> dict[str, Any]:
    delta = float(length_shift.get("delta_mean_length") or 0.0) if length_shift.get("status") == "ok" else 0.0
    top_cluster = ((covariation.get("ranked_clusters") or [{}])[0]).get("cluster_30")
    next_program = "subgroup_comparison" if abs(delta) >= 200 else "architecture_comparison"
    return {
        "query_id": query_id,
        "pattern": program_type,
        "length_shift": length_shift,
        "covariation": covariation,
        "top_cluster": top_cluster,
        "recommended_next_program": next_program,
    }
