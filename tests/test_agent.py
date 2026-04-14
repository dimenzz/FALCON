from pathlib import Path
import json
import sqlite3

from falcon.agent.reasoning import reason_candidates


def create_agent_databases(tmp_path: Path) -> tuple[Path, Path]:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    with sqlite3.connect(proteins_db) as conn:
        conn.execute(
            """
            CREATE TABLE proteins (
                protein_id TEXT PRIMARY KEY,
                contig_id TEXT NOT NULL,
                mag_id TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                strand TEXT NOT NULL,
                length INTEGER NOT NULL,
                product TEXT,
                gene_name TEXT,
                locus_tag TEXT,
                pfam TEXT,
                interpro TEXT,
                kegg TEXT,
                cog_category TEXT,
                cog_id TEXT,
                ec_number TEXT,
                eggnog TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO proteins (
                protein_id, contig_id, mag_id, start, end, strand, length,
                product, gene_name, locus_tag, pfam, interpro, kegg,
                cog_category, cog_id, ec_number, eggnog
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("target1", "contigA", "magA", 10, 18, "+", 3, "seed system protein", None, None, None, None, None, None, None, None, None),
                ("neighbor1", "contigA", "magA", 30, 38, "+", 3, "hypothetical protein", None, None, None, None, None, None, None, None, None),
                ("neighbor2", "contigA", "magA", 50, 58, "+", 3, "ABC transporter", None, None, "PF00005", "IPR003439", None, None, None, None, None),
            ],
        )
    with sqlite3.connect(clusters_db) as conn:
        conn.execute(
            """
            CREATE TABLE clusters (
                representative_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                cluster_level TEXT NOT NULL,
                PRIMARY KEY (member_id, cluster_level)
            )
            """
        )
        conn.executemany(
            "INSERT INTO clusters (representative_id, member_id, cluster_level) VALUES (?, ?, ?)",
            [
                ("target30", "target1", "30"),
                ("neighbor30", "neighbor1", "30"),
                ("neighbor30", "neighbor2", "30"),
            ],
        )
    return proteins_db, clusters_db


def create_agent_sequences(tmp_path: Path) -> tuple[Path, Path]:
    protein_fasta = tmp_path / "magA.faa"
    genome_fasta = tmp_path / "magA.fna"
    protein_manifest = tmp_path / "protein_manifest.csv"
    genome_manifest = tmp_path / "genome_manifest.csv"
    protein_fasta.write_text(
        ">target1\nMMM\n"
        ">neighbor1\nMKT\n"
        ">neighbor2\nGGG\n",
        encoding="utf-8",
    )
    genome_fasta.write_text(">contigA\n" + "ACGT" * 30 + "\n", encoding="utf-8")
    protein_manifest.write_text(f"magA,{protein_fasta}\n", encoding="utf-8")
    genome_manifest.write_text(f"magA,{genome_fasta}\n", encoding="utf-8")
    return protein_manifest, genome_manifest


def write_candidate(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "cluster_30": "neighbor30",
                "presence_contexts": 4,
                "query_contexts": 5,
                "presence_rate": 0.8,
                "fold_enrichment": 16.0,
                "q_value": 0.01,
                "examples": [
                    {
                        "context_protein_id": "target1",
                        "neighbor_protein": {"protein_id": "neighbor1", "product": "hypothetical protein"},
                        "relative_index": 1,
                        "supporting_hits": [{"query_id": "q1", "target_id": "target1"}],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_reason_candidates_writes_evidence_results_and_markdown(tmp_path: Path) -> None:
    proteins_db, clusters_db = create_agent_databases(tmp_path)
    protein_manifest, genome_manifest = create_agent_sequences(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    write_candidate(candidates_path)

    summary = reason_candidates(
        candidates_path=candidates_path,
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
        out_dir=out_dir,
        max_candidates=10,
        max_examples=5,
        include_sequences=False,
        flank_bp=3,
        sequence_max_bases=100,
    )

    results = [
        json.loads(line)
        for line in (out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["candidates_processed"] == 1
    assert summary["workflow"] == "deterministic"
    assert results[0]["candidate"]["cluster_30"] == "neighbor30"
    assert results[0]["reasoning"]["status"] == "supported"
    assert results[0]["sequence_evidence"]["protein"]["available"] is True
    assert results[0]["sequence_evidence"]["protein"]["length"] == 3
    assert "sequence" not in results[0]["sequence_evidence"]["protein"]
    assert results[0]["falsification_checklist"]
    report = Path(results[0]["report_path"]).read_text(encoding="utf-8")
    assert "Falsification Checklist" in report
    assert "neighbor30" in report
