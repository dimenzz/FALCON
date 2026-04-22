from pathlib import Path
import json

from falcon.reasoning.query_catalog import load_query_catalog
from falcon.reasoning.types import SeedSummary
from falcon.reasoning.notebook import initialize_notebook
from falcon.evidence.ledger import initialize_audit_ledger


def _write_query_catalog(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query_id": "q1",
                        "header_description": "Cas9 nuclease",
                        "function_description": "SpCas9 seed protein",
                    }
                ),
                json.dumps(
                    {
                        "query_id": "q2",
                        "header_description": "type I restriction enzyme",
                        "function_description": "Res subunit seed",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_load_query_catalog_reads_jsonl_records(tmp_path: Path) -> None:
    catalog_path = _write_query_catalog(tmp_path / "seeds.jsonl")

    catalog = load_query_catalog(catalog_path)

    assert catalog["q1"]["function_description"] == "SpCas9 seed protein"
    assert catalog["q2"]["header_description"] == "type I restriction enzyme"


def test_seed_summary_carries_query_prior_and_target_consensus() -> None:
    summary = SeedSummary.from_query_and_examples(
        query_record={
            "query_id": "q1",
            "header_description": "Cas9 nuclease",
            "function_description": "SpCas9 seed protein",
        },
        examples=[
            {
                "context": {
                    "target": {
                        "protein_id": "target1",
                        "product": "CRISPR-associated endonuclease Cas9",
                        "gene_name": "cas9",
                        "pfam": "PF01867",
                        "interpro": "IPR001234",
                        "kegg": "K19140",
                    }
                }
            },
            {
                "context": {
                    "target": {
                        "protein_id": "target2",
                        "product": "CRISPR-associated endonuclease Cas9",
                        "gene_name": "cas9",
                        "pfam": "PF01867",
                        "interpro": "IPR001234",
                        "kegg": "K19140",
                    }
                }
            },
        ],
    )

    assert summary.query_id == "q1"
    assert summary.query_prior["function_description"] == "SpCas9 seed protein"
    assert summary.query_prior["confidence"] == "soft_prior"
    assert summary.target_consensus_annotation["product"] == "CRISPR-associated endonuclease Cas9"
    assert summary.target_consensus_annotation["gene_name"] == "cas9"
    assert summary.note.startswith("Seed query descriptions are soft priors")


def test_initialize_notebook_records_seed_prior_without_hard_claim() -> None:
    summary = SeedSummary.from_query_and_examples(
        query_record={
            "query_id": "q1",
            "header_description": "Cas9 nuclease",
            "function_description": "SpCas9 seed protein",
        },
        examples=[],
    )

    notebook = initialize_notebook(seed_summary=summary, active_question="What is the candidate system role?")

    assert notebook["seed_prior"]["query_id"] == "q1"
    assert notebook["seed_prior"]["confidence"] == "soft_prior"
    assert notebook["active_question"] == "What is the candidate system role?"
    assert notebook["failed_bridges"] == []
    assert notebook["anomalies"] == []


def test_initialize_audit_ledger_graph_tracks_only_executed_fact_nodes() -> None:
    ledger = initialize_audit_ledger(
        candidate={"query_id": "q1", "cluster_30": "neighbor30"},
        seed_summary={"query_id": "q1", "query_prior": {"function_description": "SpCas9 seed protein"}},
        occurrence_examples=[{"context_protein_id": "target1", "neighbor_protein_id": "neighbor1"}],
    )

    node_types = {node["type"] for node in ledger["evidence_graph"]["nodes"]}

    assert "candidate" in node_types
    assert "seed_summary" in node_types
    assert "occurrence" in node_types
    assert "hypothesis" not in node_types
    assert "falsification_test" not in node_types
    assert "evidence_need" not in node_types
