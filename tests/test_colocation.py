from pathlib import Path
import json

from falcon.colocation.scoring import score_colocation


def write_background(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "total_90_representatives": 100,
                "clusters": [
                    {
                        "cluster_30": "neighborA",
                        "count_90_representatives": 1,
                        "background_probability": 0.01,
                    },
                    {
                        "cluster_30": "neighborB",
                        "count_90_representatives": 40,
                        "background_probability": 0.4,
                    },
                    {
                        "cluster_30": "self30",
                        "count_90_representatives": 10,
                        "background_probability": 0.1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def context_record(target: str, queries: list[str], neighbors: list[tuple[str, str]]) -> dict:
    return {
        "protein_id": target,
        "representative_30": "self30",
        "supporting_hits": [
            {
                "query_id": query,
                "target_id": target,
                "bits": 100.0,
                "evalue": 1e-10,
                "rank": 1,
            }
            for query in queries
        ],
        "context": {
            "target": {"protein_id": target, "clusters": {"30": "self30"}},
            "context": [
                {
                    "protein": {
                        "protein_id": protein_id,
                        "product": "neighbor protein",
                    },
                    "clusters": {"30": cluster_30},
                    "relative_index": index + 1,
                    "is_target": False,
                }
                for index, (protein_id, cluster_30) in enumerate(neighbors)
            ],
        },
    }


def write_contexts(path: Path) -> None:
    records = [
        context_record("target1", ["q1", "q2"], [("n1", "neighborA"), ("n2", "neighborA"), ("self-copy", "self30")]),
        context_record("target2", ["q1"], [("n3", "neighborA")]),
        context_record("target3", ["q1"], [("n4", "neighborA")]),
        context_record("target4", ["q1"], [("n5", "neighborA")]),
        context_record("target5", ["q1"], [("n6", "neighborA")]),
        context_record("target6", ["q1"], [("n7", "neighborA")]),
        context_record("target7", ["q1"], [("n8", "neighborA")]),
        context_record("target8", ["q1"], [("n9", "neighborB")]),
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_score_colocation_computes_per_query_presence_copy_count_fdr_and_examples(tmp_path: Path) -> None:
    background_path = tmp_path / "background.json"
    contexts_path = tmp_path / "cohort_contexts.jsonl"
    out_dir = tmp_path / "score"
    write_background(background_path)
    write_contexts(contexts_path)

    summary = score_colocation(
        cohort_contexts=contexts_path,
        background=background_path,
        out_dir=out_dir,
        min_contexts=3,
        min_presence_rate=0.1,
        min_fold_enrichment=2.0,
        max_qvalue=0.05,
        max_examples=5,
        no_filtering=False,
    )

    stats = [
        json.loads(line)
        for line in (out_dir / "colocation_stats.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    candidates = [
        json.loads(line)
        for line in (out_dir / "candidate_neighbors.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    q1_neighbor_a = next(row for row in stats if row["query_id"] == "q1" and row["cluster_30"] == "neighborA")

    assert summary["query_count"] == 2
    assert q1_neighbor_a["query_contexts"] == 8
    assert q1_neighbor_a["presence_contexts"] == 7
    assert q1_neighbor_a["copy_count"] == 8
    assert q1_neighbor_a["presence_rate"] == 7 / 8
    assert q1_neighbor_a["fold_enrichment"] == 87.5
    assert q1_neighbor_a["q_value"] <= 0.05
    assert len(q1_neighbor_a["examples"]) == 5
    assert all(row["cluster_30"] != "self30" for row in stats)
    assert [(row["query_id"], row["cluster_30"]) for row in candidates] == [("q1", "neighborA")]


def test_score_colocation_no_filtering_outputs_low_signal_candidates(tmp_path: Path) -> None:
    background_path = tmp_path / "background.json"
    contexts_path = tmp_path / "cohort_contexts.jsonl"
    out_dir = tmp_path / "score"
    write_background(background_path)
    write_contexts(contexts_path)

    summary = score_colocation(
        cohort_contexts=contexts_path,
        background=background_path,
        out_dir=out_dir,
        min_contexts=3,
        min_presence_rate=0.1,
        min_fold_enrichment=2.0,
        max_qvalue=0.05,
        max_examples=5,
        no_filtering=True,
    )

    candidates = [
        json.loads(line)
        for line in (out_dir / "candidate_neighbors.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["candidates"] == 3
    assert {row["cluster_30"] for row in candidates} == {"neighborA", "neighborB"}
