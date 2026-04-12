from pathlib import Path
import sqlite3

from falcon.context.extractor import extract_context


def create_proteins_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
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
        conn.execute(
            """
            CREATE TABLE contigs (
                contig_id TEXT PRIMARY KEY,
                mag_id TEXT NOT NULL,
                length INTEGER NOT NULL,
                taxonomy TEXT,
                environment TEXT
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
                ("p1", "contigA", "magA", 100, 160, "+", 20, "alpha", None, None, None, None, None, None, None, None, None),
                ("p2", "contigA", "magA", 200, 260, "+", 20, "beta", None, None, "PF00001", None, None, None, None, None, None),
                ("p3", "contigA", "magA", 300, 390, "-", 30, "target", "gene3", None, None, "IPR000003", None, None, None, None, None),
                ("p4", "contigA", "magA", 430, 470, "+", 13, "delta", None, None, None, None, None, None, None, None, None),
                ("p5", "contigA", "magA", 520, 600, "+", 26, "epsilon", None, None, None, None, None, None, None, None, None),
            ],
        )


def create_clusters_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
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
                ("c90_p2", "p2", "90"),
                ("c30_p2", "p2", "30"),
                ("c90_p3", "p3", "90"),
                ("c30_p3", "p3", "30"),
                ("c90_p4", "p4", "90"),
                ("c30_p4", "p4", "30"),
            ],
        )


def test_gene_window_context_returns_occurrence_neighbors_and_clusters(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    create_proteins_db(proteins_db)
    create_clusters_db(clusters_db)

    result = extract_context(
        protein_id="p3",
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        window_mode="genes",
        upstream=1,
        downstream=1,
        include_clusters=True,
    )

    assert result["target"]["protein_id"] == "p3"
    assert [item["protein"]["protein_id"] for item in result["context"]] == ["p2", "p3", "p4"]
    assert [item["relative_index"] for item in result["context"]] == [-1, 0, 1]
    assert result["context"][0]["clusters"]["90"] == "c90_p2"
    assert result["context"][0]["clusters"]["30"] == "c30_p2"


def test_bp_span_context_returns_overlapping_occurrences(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    create_proteins_db(proteins_db)

    result = extract_context(
        protein_id="p3",
        proteins_db=proteins_db,
        window_mode="bp",
        bp_upstream=80,
        bp_downstream=30,
        include_clusters=False,
    )

    assert result["query"]["window"] == {"start": 220, "end": 420}
    assert [item["protein"]["protein_id"] for item in result["context"]] == ["p2", "p3"]
    assert "clusters" not in result["context"][0]
