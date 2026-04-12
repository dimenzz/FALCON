# FALCON Phase 2 Homology and Cohorts Design

## Summary

Phase 2 adds FASTA-based homology search and context cohort construction. It does not implement co-localization statistics, candidate scoring, agent reasoning, or InterProScan execution.

## Interfaces

- `falcon homology search` parses seed FASTA, optional seed metadata TSV, runs MMseqs, and writes run artifacts.
- `falcon cohort build` reads parsed hits and extracts genomic context for deduplicated 90% representative targets.

Seed metadata is a two-column TSV: `query_id` and `function_description`. Metadata descriptions override FASTA header descriptions. Missing metadata is allowed; missing descriptions are reported as warnings.

## Cluster Policy

The default search level is 90. Search level 30 is supported. If hits come from the 30% database, cohort construction expands each 30% representative to its 90% representative members. If hits come from the 90% database and `expand_30_contexts` is enabled, cohort construction expands to sibling 90% representatives in the same 30% cluster.

Phase 2 does not expand 90% representatives to raw redundant members at `cluster_level=90`.

## Artifacts

`falcon homology search` writes `raw_hits.tsv`, `hits.jsonl`, `seeds.jsonl`, and `summary.json`.

`falcon cohort build` writes `cohort_members.jsonl`, `cohort_contexts.jsonl`, and `cohort_summary.json`.

## Tool Threads

MMseqs search should pass the configured thread count as `--threads`. InterProScan is not executed in Phase 2, but its adapter should preserve the configured thread count as `--cpu` for later annotation workflows.
