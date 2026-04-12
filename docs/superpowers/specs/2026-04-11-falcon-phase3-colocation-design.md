# FALCON Phase 3 Co-Localization Design

## Summary

Phase 3 adds deterministic co-localization statistics and ranked candidate neighbor output. It does not implement agent reasoning, InterProScan execution, evidence graphs, or final reports.

## Background

`falcon background build` computes exact genome-wide abundance of 30% clusters among 90% representatives using `clusters.db`. It writes JSON and TSV artifacts that can be reused by later scoring runs.

## Scoring

`falcon colocation score` reads Phase 2 `cohort_contexts.jsonl`, assigns contexts to all supporting query IDs, excludes the target context's own 30% cluster, and aggregates neighbor proteins by 30% cluster. The main observation is per-context presence; copy count is retained as supporting evidence.

The scorer reports presence rate, background probability, fold enrichment, Fisher exact p-value, BH-FDR q-value, and up to five example neighbor proteins per candidate by default.

## Outputs

The scorer writes `colocation_stats.jsonl`, `candidate_neighbors.jsonl`, `candidate_neighbors.tsv`, and `colocation_summary.json`.
