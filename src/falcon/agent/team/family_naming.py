from __future__ import annotations

from collections import defaultdict
from typing import Any

from falcon.tools.accession_enrichment import AccessionEnricher

SOURCE_PRIORITY = ("COG", "KEGG", "Pfam", "InterPro")
_PRIORITY_INDEX = {source: index for index, source in enumerate(SOURCE_PRIORITY)}


def aggregate_family_terms(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"sources": set(), "supporting_accessions": set()})
    for record in records:
        accession = str(record.get("accession") or "").strip()
        source = str(record.get("source") or "").strip()
        for term in record.get("family_terms") or []:
            normalized_term = str(term or "").strip()
            if not normalized_term:
                continue
            grouped[normalized_term]["sources"].add(source)
            if accession:
                grouped[normalized_term]["supporting_accessions"].add(accession)
    return [
        {
            "term": term,
            "sources": sorted(payload["sources"]),
            "supporting_accessions": sorted(payload["supporting_accessions"]),
        }
        for term, payload in sorted(grouped.items(), key=lambda item: item[0])
    ]


def select_family_term(aggregated_terms: list[dict[str, Any]]) -> dict[str, Any]:
    if not aggregated_terms:
        return {
            "selected_family_term": None,
            "selected_source": None,
            "supporting_accessions": [],
            "discarded_terms": [],
        }

    ranked = sorted(
        (_normalize_term(term) for term in aggregated_terms),
        key=lambda item: (_best_source_rank(item["sources"]), item["term"]),
    )
    selected = ranked[0]
    return {
        "selected_family_term": selected["term"],
        "selected_source": _highest_priority_source(selected["sources"]),
        "supporting_accessions": list(selected["supporting_accessions"]),
        "discarded_terms": [
            {
                "term": term["term"],
                "sources": list(term["sources"]),
                "supporting_accessions": list(term["supporting_accessions"]),
            }
            for term in ranked[1:]
        ],
    }


def resolve_family_naming(
    *,
    representative_neighbor: dict[str, Any],
    accession_enricher: AccessionEnricher | None,
    accession_cache_dir: str | None = None,
) -> dict[str, Any]:
    if accession_enricher is None:
        return {
            "representative_neighbor_id": representative_neighbor.get("protein_id"),
            "accession_records": [],
            "aggregated_terms": [],
            "selection": select_family_term([]),
        }
    accession_records = accession_enricher.enrich_candidate(
        representative_neighbor,
        cache_dir=accession_cache_dir,
    )
    aggregated_terms = aggregate_family_terms(accession_records)
    return {
        "representative_neighbor_id": representative_neighbor.get("protein_id"),
        "accession_records": accession_records,
        "aggregated_terms": aggregated_terms,
        "selection": select_family_term(aggregated_terms),
    }


def _normalize_term(term: dict[str, Any]) -> dict[str, Any]:
    return {
        "term": str(term.get("term") or "").strip(),
        "sources": sorted({str(source).strip() for source in term.get("sources") or [] if str(source).strip()}),
        "supporting_accessions": sorted(
            {str(accession).strip() for accession in term.get("supporting_accessions") or [] if str(accession).strip()}
        ),
    }


def _best_source_rank(sources: list[str]) -> int:
    if not sources:
        return len(SOURCE_PRIORITY)
    return min(_PRIORITY_INDEX.get(source, len(SOURCE_PRIORITY)) for source in sources)


def _highest_priority_source(sources: list[str]) -> str | None:
    if not sources:
        return None
    return min(sources, key=lambda source: (_PRIORITY_INDEX.get(source, len(SOURCE_PRIORITY)), source))
