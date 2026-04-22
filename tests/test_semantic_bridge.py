from falcon.tools.accession_enrichment import AccessionEnricher
from falcon.tools.semantic_bridge import resolve_semantic_bridge


def test_resolve_semantic_bridge_enriches_accessions_and_returns_family_terms() -> None:
    enricher = AccessionEnricher(
        fetchers={
            "Pfam": lambda accession: {
                "source": "Pfam",
                "accession": accession,
                "family_terms": ["Restriction endonuclease-associated family"],
                "raw_label": "restriction endonuclease-associated family",
            }
        }
    )

    result = resolve_semantic_bridge(
        accessions_by_source={"Pfam": ["PF04851"]},
        accession_enricher=enricher,
    )

    assert result["status"] == "ok"
    assert result["records"][0]["accession"] == "PF04851"
    assert result["summary"]["resolved_family_terms"] == ["Restriction endonuclease-associated family"]

