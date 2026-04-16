from __future__ import annotations

from falcon.agent.team.family_naming import aggregate_family_terms, select_family_term


def test_aggregate_family_terms_merges_same_term_across_sources_and_keeps_family_level_only() -> None:
    aggregated = aggregate_family_terms(
        [
            {
                "source": "Pfam",
                "accession": "PF09711",
                "family_terms": ["Csn2"],
                "raw_label": "CRISPR-associated protein Csn2",
            },
            {
                "source": "InterPro",
                "accession": "IPR010146",
                "family_terms": ["Csn2"],
                "raw_label": "CRISPR-associated protein Csn2 family",
            },
            {
                "source": "KEGG",
                "accession": "K19137",
                "family_terms": ["Csn2"],
                "raw_label": "Csn2 family protein",
            },
            {
                "source": "InterPro",
                "accession": "IPR999999",
                "family_terms": [],
                "raw_label": "adaptation accessory factor",
            },
        ]
    )

    assert aggregated == [
        {
            "term": "Csn2",
            "sources": ["InterPro", "KEGG", "Pfam"],
            "supporting_accessions": ["IPR010146", "K19137", "PF09711"],
        }
    ]


def test_select_family_term_obeys_source_priority_and_preserves_discarded_terms() -> None:
    selection = select_family_term(
        [
            {
                "term": "Cas2",
                "sources": ["Pfam", "InterPro"],
                "supporting_accessions": ["PF09827", "IPR007220"],
            },
            {
                "term": "Cas2-like",
                "sources": ["InterPro"],
                "supporting_accessions": ["IPR043656"],
            },
            {
                "term": "Cas2",
                "sources": ["COG"],
                "supporting_accessions": ["COG1518"],
            },
        ]
    )

    assert selection == {
        "selected_family_term": "Cas2",
        "selected_source": "COG",
        "supporting_accessions": ["COG1518"],
        "discarded_terms": [
            {
                "term": "Cas2",
                "sources": ["InterPro", "Pfam"],
                "supporting_accessions": ["IPR007220", "PF09827"],
            },
            {
                "term": "Cas2-like",
                "sources": ["InterPro"],
                "supporting_accessions": ["IPR043656"],
            },
        ],
    }
