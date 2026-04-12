from __future__ import annotations

from pathlib import Path
from typing import Any

from falcon.data.clusters import ClusterRepository
from falcon.data.proteins import ProteinRepository
from falcon.models import WindowMode


def extract_context(
    *,
    protein_id: str,
    proteins_db: Path | str,
    clusters_db: Path | str | None = None,
    window_mode: str = WindowMode.GENES.value,
    upstream: int = 5,
    downstream: int = 5,
    bp_upstream: int = 5000,
    bp_downstream: int = 5000,
    include_clusters: bool = False,
) -> dict[str, Any]:
    with ProteinRepository(proteins_db) as proteins:
        target = proteins.get(protein_id)
        contig_proteins = proteins.contig_proteins(target["contig_id"])

    target_index = _target_index(contig_proteins, protein_id)
    mode = WindowMode(window_mode)

    if mode is WindowMode.GENES:
        start_index = max(0, target_index - upstream)
        end_index = min(len(contig_proteins), target_index + downstream + 1)
        selected = contig_proteins[start_index:end_index]
        query_window: dict[str, int] = {"upstream": upstream, "downstream": downstream}
    else:
        window_start = max(1, int(target["start"]) - bp_upstream)
        window_end = int(target["end"]) + bp_downstream
        selected = [
            protein
            for protein in contig_proteins
            if int(protein["end"]) >= window_start and int(protein["start"]) <= window_end
        ]
        query_window = {"start": window_start, "end": window_end}

    clusters_by_member: dict[str, dict[str, str]] = {}
    if include_clusters and clusters_db is not None:
        with ClusterRepository(clusters_db) as clusters:
            clusters_by_member = clusters.representatives_for_members(
                [protein["protein_id"] for protein in selected]
            )

    context = []
    for protein in selected:
        item: dict[str, Any] = {
            "protein": protein,
            "relative_index": _target_index(contig_proteins, protein["protein_id"]) - target_index,
            "is_target": protein["protein_id"] == protein_id,
        }
        if include_clusters and clusters_db is not None:
            item["clusters"] = clusters_by_member.get(protein["protein_id"], {})
        context.append(item)

    result_target = dict(target)
    if include_clusters and clusters_db is not None:
        result_target["clusters"] = clusters_by_member.get(protein_id, {})

    return {
        "query": {
            "protein_id": protein_id,
            "window_mode": mode.value,
            "window": query_window,
        },
        "target": result_target,
        "context": context,
    }


def _target_index(proteins: list[dict[str, Any]], protein_id: str) -> int:
    for index, protein in enumerate(proteins):
        if protein["protein_id"] == protein_id:
            return index
    raise ValueError(f"Protein {protein_id!r} was not found in its contig context")
