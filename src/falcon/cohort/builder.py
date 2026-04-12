from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import json

from falcon.context.extractor import extract_context
from falcon.data.clusters import ClusterRepository
from falcon.homology.search import HomologyHit, read_hits_jsonl, write_jsonl


def build_context_cohort(
    *,
    hits_path: Path | str,
    proteins_db: Path | str,
    clusters_db: Path | str,
    out_dir: Path | str,
    search_level: int | None = None,
    expand_30_contexts: bool = False,
    window_mode: str = "genes",
    upstream: int = 5,
    downstream: int = 5,
    bp_upstream: int = 5000,
    bp_downstream: int = 5000,
) -> dict[str, Any]:
    hits = read_hits_jsonl(hits_path)
    resolved_search_level = _resolve_search_level(hits, search_level)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    member_support: dict[str, list[HomologyHit]] = defaultdict(list)
    representative_30: dict[str, str | None] = {}
    with ClusterRepository(clusters_db) as clusters:
        for hit in hits:
            for member_id, rep30 in _context_targets_for_hit(
                hit,
                clusters=clusters,
                search_level=resolved_search_level,
                expand_30_contexts=expand_30_contexts,
            ):
                member_support[member_id].append(hit)
                representative_30[member_id] = rep30

    members = [
        {
            "protein_id": protein_id,
            "representative_30": representative_30.get(protein_id),
            "supporting_hits": [hit.to_dict() for hit in supporting_hits],
        }
        for protein_id, supporting_hits in sorted(member_support.items())
    ]

    contexts = []
    for member in members:
        context = extract_context(
            protein_id=member["protein_id"],
            proteins_db=proteins_db,
            clusters_db=clusters_db,
            window_mode=window_mode,
            upstream=upstream,
            downstream=downstream,
            bp_upstream=bp_upstream,
            bp_downstream=bp_downstream,
            include_clusters=True,
        )
        contexts.append(
            {
                "protein_id": member["protein_id"],
                "representative_30": member["representative_30"],
                "supporting_hits": member["supporting_hits"],
                "context": context,
            }
        )

    write_jsonl(members, output_dir / "cohort_members.jsonl")
    write_jsonl(contexts, output_dir / "cohort_contexts.jsonl")
    summary = {
        "hits": len(hits),
        "search_level": resolved_search_level,
        "expand_30_contexts": expand_30_contexts,
        "context_targets": len(members),
        "cohort_members": str(output_dir / "cohort_members.jsonl"),
        "cohort_contexts": str(output_dir / "cohort_contexts.jsonl"),
    }
    (output_dir / "cohort_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _context_targets_for_hit(
    hit: HomologyHit,
    *,
    clusters: ClusterRepository,
    search_level: int,
    expand_30_contexts: bool,
) -> list[tuple[str, str | None]]:
    if search_level == 30:
        members = clusters.members_for_representative(hit.target_id, 30)
        return [(member_id, hit.target_id) for member_id in members]

    representative_30 = clusters.representative_for_member(hit.target_id, 30)
    if expand_30_contexts and representative_30 is not None:
        return [
            (member_id, representative_30)
            for member_id in clusters.members_for_representative(representative_30, 30)
        ]
    return [(hit.target_id, representative_30)]


def _resolve_search_level(hits: list[HomologyHit], search_level: int | None) -> int:
    if search_level is not None:
        return int(search_level)
    if hits:
        return hits[0].search_level
    return 90
