from __future__ import annotations

from typing import Any

from falcon.tools.accession_enrichment import AccessionEnricher


def resolve_semantic_bridge(
    *,
    accessions_by_source: dict[str, list[str]],
    accession_enricher: AccessionEnricher,
    cache_dir: str | None = None,
) -> dict[str, Any]:
    records = accession_enricher.enrich_accessions(accessions_by_source, cache_dir=cache_dir)
    resolved_family_terms = sorted(
        {
            str(term)
            for record in records
            for term in (record.get("family_terms") or [])
            if str(term).strip()
        }
    )
    return {
        "tool": "resolve_semantic_bridge",
        "status": "ok" if records else "unresolved",
        "records": records,
        "summary": {
            "sources": sorted(accessions_by_source),
            "accession_count": sum(len(values) for values in accessions_by_source.values()),
            "resolved_family_terms": resolved_family_terms,
        },
    }
