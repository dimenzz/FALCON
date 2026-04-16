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
- Tool layer: manifest-described, allowlisted tool execution with capability metadata, stdout/stderr log artifacts, structured traces, progress events, cost-aware scheduling, and optional reviewed dynamic Python tools.
- Agent layer: deterministic evidence packet construction, optional single-LLM falsification loop, and a candidate-level multi-agent evidence-graph workflow for literature grounding, hypothesis generation, evidence-needs derivation, manifest-driven tool planning, dynamic tool fallback, audit, revision, and synthesis.
- Reporting layer: Markdown rendering for agent evidence reports.

Tool execution parameters, including CPU thread counts, belong in configuration and must remain overridable from the CLI. MMseqs search uses `homology.threads`; InterProScan adapters use `tools.interproscan_threads`. External tool stdout and stderr must be captured into logs instead of being mixed with user-facing CLI output. Long-running agent tools emit lifecycle and heartbeat events to `agent_events.jsonl` and, when `runtime.progress` is true, to CLI stderr.

The default Agent mode is deterministic. Optional LLM modes use an OpenAI-compatible Chat Completions provider, centralized YAML prompt packs, pydantic-validated JSON actions, trace artifacts, and per-candidate ledgers. The team workflow now front-loads deterministic accession enrichment and family selection, then runs scoped literature grounding, structured `1 main + 1 competing` working hypotheses, evidence-need planning, deterministic tool summaries, audited revision, and final synthesis. Role prompts load from `agent.team.prompt_dir`, consume role-specific context packs with a `context_workbench`, validate tool plans against `agent.team.tool_manifest`, and can run reviewed dynamic Python tools only when `agent.dynamic_tools.enabled` is true.

## Cluster vs Occurrence Boundary

FALCON uses clusters to reduce redundancy and compute statistical effects, but uses real occurrences for evidence.

- Cluster layer: `clusters.db` maps `member_id` to `representative_id` at cluster levels such as 90 and 30.
- Occurrence layer: `proteins.db` stores real protein rows with contig, MAG, coordinates, strand, and annotations.

Future co-localization statistics should merge neighbor proteins to 30% clusters. Agent reasoning should then return to occurrence-level examples so conclusions can be audited against real genomic contexts.

For the Phase 2 cohort builder, "occurrence" means a real protein row that is also a 90% representative. FALCON does not expand to all raw members of each 90% cluster at this stage; that avoids reintroducing oversampled redundant contexts.

Phase 3 compares neighbor 30% cluster presence in those contexts against genome-wide 30% cluster abundance among 90% representatives. It reports deterministic statistics and candidate examples.

Phase 4 MVP reads those candidate examples, returns to occurrence-level proteins, hydrates evidence from `proteins.db`, `clusters.db`, and manifest-backed FASTA files, then writes evidence packets and Markdown reports. In single-agent LLM mode, the model can only request read-only observations from that hydrated evidence packet and must emit auditable JSON actions. In team mode, an orchestrated ledger loop grounds the candidate in literature before generating hypotheses, derives hypothesis-specific falsification tests, routes evidence needs through a manifest-derived tool catalog, validates tool capability matches, optionally falls back to reviewed dynamic Python tools, audits evidence, revises hypotheses, and writes a per-candidate JSON ledger with an evidence graph.

## Future Pipeline

1. Search seed protein homologs using the selected MMseqs database.
2. Map hits to cluster representatives and occurrence members.
3. Extract occurrence contexts from `proteins.db`.
4. Aggregate neighbor proteins to 30% clusters for co-localization statistics.
5. Select high-effect neighbor clusters.
6. Build deterministic evidence packets for individual candidate neighbor proteins.
7. Extend the current LLM-backed falsification-first reasoning with richer fixed tools and promoted dynamic tools.
8. Generate final reports with evidence graph, contradiction ledger, tool traces, and uncertainty.
