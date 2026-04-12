from pathlib import Path
import json
import sqlite3

from falcon.cohort.builder import build_context_cohort
from falcon.homology.search import HomologyHit, write_hits_jsonl


def create_cohort_proteins_db(path: Path) -> None:
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
        rows = []
        for prefix in ("rep90a", "rep90b"):
            rows.extend(
                [
                    (f"{prefix}_left", f"{prefix}_contig", "mag", 10, 50, "+", 13, "left", None, None, None, None, None, None, None, None, None),
                    (prefix, f"{prefix}_contig", "mag", 100, 180, "+", 26, "target", None, None, None, None, None, None, None, None, None),
                    (f"{prefix}_right", f"{prefix}_contig", "mag", 220, 300, "+", 26, "right", None, None, None, None, None, None, None, None, None),
                ]
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
            rows,
        )


def create_cohort_clusters_db(path: Path) -> None:
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
                ("rep30x", "rep90a", "30"),
                ("rep30x", "rep90b", "30"),
                ("rep90a", "rep90a_raw1", "90"),
                ("rep90b", "rep90b_raw1", "90"),
            ],
        )


def make_hit(query_id: str, target_id: str, search_level: int, rank: int = 1) -> HomologyHit:
    return HomologyHit(
        query_id=query_id,
        target_id=target_id,
        pident=90.0,
        alnlen=100,
        qcov=0.9,
        tcov=0.8,
        evalue=1e-10,
        bits=120.0,
        qlen=110,
        tlen=125,
        search_level=search_level,
        rank=rank,
    )


def test_build_context_cohort_uses_90_representatives_without_raw_expansion(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    hits_path = tmp_path / "hits.jsonl"
    out_dir = tmp_path / "cohort"
    create_cohort_proteins_db(proteins_db)
    create_cohort_clusters_db(clusters_db)
    write_hits_jsonl(
        [
            make_hit("q1", "rep90a", 90, rank=1),
            make_hit("q2", "rep90a", 90, rank=1),
        ],
        hits_path,
    )

    summary = build_context_cohort(
        hits_path=hits_path,
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        out_dir=out_dir,
        search_level=90,
        expand_30_contexts=False,
        upstream=1,
        downstream=1,
    )

    contexts = [
        json.loads(line)
        for line in (out_dir / "cohort_contexts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["context_targets"] == 1
    assert contexts[0]["protein_id"] == "rep90a"
    assert [hit["query_id"] for hit in contexts[0]["supporting_hits"]] == ["q1", "q2"]
    assert all(item["protein"]["protein_id"] != "rep90a_raw1" for item in contexts[0]["context"]["context"])


def test_build_context_cohort_expands_30_hits_to_90_representatives(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    hits_path = tmp_path / "hits.jsonl"
    out_dir = tmp_path / "cohort"
    create_cohort_proteins_db(proteins_db)
    create_cohort_clusters_db(clusters_db)
    write_hits_jsonl([make_hit("q1", "rep30x", 30)], hits_path)

    summary = build_context_cohort(
        hits_path=hits_path,
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        out_dir=out_dir,
        search_level=30,
        expand_30_contexts=False,
        upstream=1,
        downstream=1,
    )

    members = [
        json.loads(line)
        for line in (out_dir / "cohort_members.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["context_targets"] == 2
    assert [member["protein_id"] for member in members] == ["rep90a", "rep90b"]
    assert {member["representative_30"] for member in members} == {"rep30x"}


def test_build_context_cohort_expands_90_hits_to_30_siblings_when_enabled(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    hits_path = tmp_path / "hits.jsonl"
    out_dir = tmp_path / "cohort"
    create_cohort_proteins_db(proteins_db)
    create_cohort_clusters_db(clusters_db)
    write_hits_jsonl([make_hit("q1", "rep90a", 90)], hits_path)

    summary = build_context_cohort(
        hits_path=hits_path,
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        out_dir=out_dir,
        search_level=90,
        expand_30_contexts=True,
        upstream=1,
        downstream=1,
    )

    assert summary["context_targets"] == 2
