from falcon.literature.search import LiteratureRecord, merge_literature_results


def test_merge_literature_results_deduplicates_by_pmid_then_doi() -> None:
    merged = merge_literature_results(
        [
            LiteratureRecord(
                source="europe_pmc",
                title="Cas9 recognizes PAM motifs",
                abstract="Cas9 binding depends on PAM motifs.",
                pmid="123",
                doi="10.1/cas9",
            ),
            LiteratureRecord(
                source="europe_pmc",
                title="Distinct CRISPR system",
                abstract="A different defense system.",
                doi="10.1/other",
            ),
        ],
        [
            LiteratureRecord(
                source="pubmed",
                title="Cas9 recognizes PAM motifs",
                abstract="Duplicate PubMed record.",
                pmid="123",
                doi="10.1/cas9",
            ),
            LiteratureRecord(
                source="pubmed",
                title="Distinct CRISPR system",
                abstract="Duplicate DOI record.",
                doi="10.1/other",
            ),
        ],
    )

    assert len(merged) == 2
    assert merged[0].sources == ("europe_pmc", "pubmed")
    assert merged[1].sources == ("europe_pmc", "pubmed")
