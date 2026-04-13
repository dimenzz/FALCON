# FALCON Architecture

FALCON is designed around a falsification-first discovery loop. The full system starts from seed proteins, searches homologs, extracts genomic context, scores co-localized neighbors, and then reasons over individual candidate neighbor proteins using explicit falsification tests.

## MVP Architecture

The first implementation keeps the system small and executable:

- CLI: user-facing commands for configuration, inspection, and occurrence context extraction.
- Config: YAML plus CLI overrides, with precedence `CLI > YAML > defaults`.
- Data layer: SQLite repositories, manifest readers, and sequence-path access.
- Context layer: occurrence-level genomic neighborhood extraction.
- Homology layer: FASTA seed parsing, MMseqs search execution, and parsed hit artifacts.
- Cohort layer: mapping search hits to 90% representative context targets.
- Co-location layer: deterministic neighbor 30% cluster statistics and candidate ranking.
- Tool layer: quiet external command execution with stdout/stderr log artifacts and structured traces.
- Agent layer: deterministic evidence packet construction plus optional replayable LLM falsification loop for candidate neighbor proteins.
- Reporting layer: Markdown rendering for agent evidence reports.

Tool execution parameters, including CPU thread counts, belong in configuration and must remain overridable from the CLI. MMseqs search uses `homology.threads`; InterProScan adapters use `tools.interproscan_threads`. External tool stdout and stderr must be captured into logs instead of being mixed with user-facing CLI output.

The default Agent mode is deterministic. Optional LLM modes use an OpenAI-compatible Chat Completions provider, centralized YAML prompt packs, allowlisted JSON actions, and trace artifacts. The Agent MVP still does not run InterProScan automatically, perform web or literature retrieval, or generate dynamic tools.

## Cluster vs Occurrence Boundary

FALCON uses clusters to reduce redundancy and compute statistical effects, but uses real occurrences for evidence.

- Cluster layer: `clusters.db` maps `member_id` to `representative_id` at cluster levels such as 90 and 30.
- Occurrence layer: `proteins.db` stores real protein rows with contig, MAG, coordinates, strand, and annotations.

Future co-localization statistics should merge neighbor proteins to 30% clusters. Agent reasoning should then return to occurrence-level examples so conclusions can be audited against real genomic contexts.

For the Phase 2 cohort builder, "occurrence" means a real protein row that is also a 90% representative. FALCON does not expand to all raw members of each 90% cluster at this stage; that avoids reintroducing oversampled redundant contexts.

Phase 3 compares neighbor 30% cluster presence in those contexts against genome-wide 30% cluster abundance among 90% representatives. It reports deterministic statistics and candidate examples.

Phase 4 MVP reads those candidate examples, returns to occurrence-level proteins, hydrates evidence from `proteins.db`, `clusters.db`, and manifest-backed FASTA files, then writes evidence packets and Markdown reports. In LLM mode, the model can only request read-only observations from that hydrated evidence packet and must emit auditable JSON actions.

## Future Pipeline

1. Search seed protein homologs using the selected MMseqs database.
2. Map hits to cluster representatives and occurrence members.
3. Extract occurrence contexts from `proteins.db`.
4. Aggregate neighbor proteins to 30% clusters for co-localization statistics.
5. Select high-effect neighbor clusters.
6. Build deterministic evidence packets for individual candidate neighbor proteins.
7. Extend the current LLM-backed falsification-first reasoning with optional annotation tools in a later phase.
8. Generate final reports with evidence graph, contradiction ledger, tool traces, and uncertainty.
