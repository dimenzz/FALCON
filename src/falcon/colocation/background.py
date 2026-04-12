from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from falcon.data.sqlite import connect_readonly


def build_background_abundance(*, clusters_db: Path | str, out_dir: Path | str) -> dict[str, Any]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with connect_readonly(clusters_db) as connection:
        rows = connection.execute(
            """
            SELECT representative_id, COUNT(*) AS count_90_representatives
            FROM clusters
            WHERE cluster_level = '30'
            GROUP BY representative_id
            ORDER BY representative_id
            """
        ).fetchall()

    total = sum(int(row["count_90_representatives"]) for row in rows)
    clusters = []
    for row in rows:
        cluster_30 = row["representative_id"]
        count = int(row["count_90_representatives"])
        counts[cluster_30] = count
        clusters.append(
            {
                "cluster_30": cluster_30,
                "count_90_representatives": count,
                "total_90_representatives": total,
                "background_probability": count / total if total else 0.0,
            }
        )

    payload = {
        "total_90_representatives": total,
        "clusters": clusters,
    }
    json_path = output_dir / "background_30_abundance.json"
    tsv_path = output_dir / "background_30_abundance.tsv"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with tsv_path.open("w", encoding="utf-8") as handle:
        handle.write("cluster_30\tcount_90_representatives\ttotal_90_representatives\tbackground_probability\n")
        for row in clusters:
            handle.write(
                f"{row['cluster_30']}\t{row['count_90_representatives']}\t"
                f"{row['total_90_representatives']}\t{row['background_probability']}\n"
            )

    return {
        "total_90_representatives": total,
        "clusters": len(clusters),
        "background_json": str(json_path),
        "background_tsv": str(tsv_path),
    }
