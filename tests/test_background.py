from pathlib import Path
import json
import sqlite3

from falcon.colocation.background import build_background_abundance


def create_background_clusters_db(path: Path) -> None:
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
                ("c30a", "rep90a", "30"),
                ("c30a", "rep90b", "30"),
                ("c30b", "rep90c", "30"),
                ("rep90a", "raw_a1", "90"),
            ],
        )


def test_build_background_abundance_counts_30_clusters_over_90_representatives(tmp_path: Path) -> None:
    clusters_db = tmp_path / "clusters.db"
    out_dir = tmp_path / "background"
    create_background_clusters_db(clusters_db)

    summary = build_background_abundance(clusters_db=clusters_db, out_dir=out_dir)

    payload = json.loads((out_dir / "background_30_abundance.json").read_text(encoding="utf-8"))
    rows = {row["cluster_30"]: row for row in payload["clusters"]}
    assert summary["total_90_representatives"] == 3
    assert rows["c30a"]["count_90_representatives"] == 2
    assert rows["c30a"]["background_probability"] == 2 / 3
    assert rows["c30b"]["count_90_representatives"] == 1
    assert "raw_a1" not in rows
    assert (out_dir / "background_30_abundance.tsv").exists()
