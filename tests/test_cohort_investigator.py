from falcon.reasoning.cohort_investigator import (
    compare_candidate_lengths,
    compare_neighbor_covariation,
    summarize_cohort_patterns,
)


def test_compare_candidate_lengths_reports_shift_between_groups() -> None:
    result = compare_candidate_lengths(
        with_pattern=[{"protein_length": 1500}, {"protein_length": 1490}, {"protein_length": 1510}],
        without_pattern=[{"protein_length": 1100}, {"protein_length": 1090}, {"protein_length": 1110}],
    )

    assert result["status"] == "ok"
    assert result["delta_mean_length"] > 300


def test_summarize_cohort_patterns_returns_pattern_summary_and_next_step() -> None:
    summary = summarize_cohort_patterns(
        query_id="q1",
        program_type="cohort_anomaly_scan",
        length_shift={"status": "ok", "delta_mean_length": 380.0},
        covariation=compare_neighbor_covariation(
            candidates=[
                {"cluster_30": "nag", "presence_contexts": 12},
                {"cluster_30": "nag", "presence_contexts": 10},
                {"cluster_30": "other", "presence_contexts": 2},
            ]
        ),
    )

    assert summary["query_id"] == "q1"
    assert summary["pattern"] == "cohort_anomaly_scan"
    assert summary["recommended_next_program"] in {"subgroup_comparison", "architecture_comparison"}
