from __future__ import annotations

from falcon.tools.interproscan import parse_interproscan_tsv


def test_parse_interproscan_tsv_extracts_domain_records() -> None:
    payload = "\n".join(
        [
            "neighbor1\tmd5\t321\tPfam\tPF09711\tCRISPR-associated protein Csn2\t12\t210\t42.0\tT\t2026-04-15\tIPR010146\tCRISPR-associated protein Csn2 family\tGO:0003677\t-",
            "neighbor1\tmd5\t321\tSUPERFAMILY\tSSF12345\tAccessory fold\t50\t280\t88.0\tT\t2026-04-15\t-\t-\t-\t-",
        ]
    )

    records = parse_interproscan_tsv(payload)

    assert records == [
        {
            "analysis": "Pfam",
            "signature_accession": "PF09711",
            "signature_description": "CRISPR-associated protein Csn2",
            "start": 12,
            "end": 210,
            "interpro_accession": "IPR010146",
            "interpro_description": "CRISPR-associated protein Csn2 family",
        },
        {
            "analysis": "SUPERFAMILY",
            "signature_accession": "SSF12345",
            "signature_description": "Accessory fold",
            "start": 50,
            "end": 280,
            "interpro_accession": None,
            "interpro_description": None,
        },
    ]
