# FALCON Phase 4 Agent Evidence and Tool Logging Design

## Summary

Phase 4 MVP adds deterministic candidate evidence construction and quiet external tool logging. It does not add LLM calls, dynamic tool generation, or automatic InterProScan execution.

## Tool Execution

External tools run through a shared runner that captures stdout and stderr into log files under `runtime.log_dir`. CLI output remains FALCON-owned JSON/YAML. Tool failures report the exit code and log paths. MMseqs homology search uses this runner first; future InterProScan execution should reuse it.

## Sequence Access

Sequence lookup is a data-layer service backed by the existing two-column manifests. It supports protein FASTA lookup by `protein_id` and DNA span lookup by `protein_id` plus flank length. DNA coordinates are 1-based inclusive. Negative-strand DNA is returned in protein orientation by default, with original coordinates retained in metadata. The first implementation is a streaming FASTA reader with a replaceable boundary for a future indexed backend.

## Agent MVP

`falcon agent reason` reads Phase 3 `candidate_neighbors.jsonl`, processes candidates independently, hydrates occurrence examples from SQLite and sequence manifests, and writes `agent_results.jsonl`, `agent_summary.json`, and per-candidate Markdown reports.

The reasoning is rule-based and evidence-conservative. It emits support states such as `supported`, `weak`, `conflicting`, and `insufficient`, plus a falsification checklist and uncertainties. Missing evidence is recorded rather than guessed.
