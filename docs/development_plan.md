# FALCON Development Plan

## Phase 1: CLI and Data Skeleton

Implement the executable project skeleton:

- Python `src/` layout.
- `uv` project metadata.
- YAML configuration with CLI overrides.
- Data source inspection.
- Occurrence-level context extraction.
- Fixture-based tests.

## Phase 2: Homology and Context Cohorts

Add MMseqs search wrappers and cluster expansion policies:

- Search against 90% or 30% databases.
- Map hits to cluster representatives and occurrence members.
- Extract occurrence contexts for the selected hit cohort.
- Keep cohort context targets at the 90% representative level to avoid raw-member oversampling.

## Phase 3: Co-localization Statistics

Compute cluster-level co-localization effects:

- Merge neighbor proteins into 30% clusters.
- Estimate association strength between seed-hit contexts and neighbor clusters.
- Emit ranked candidate neighbor proteins with occurrence examples.
- Use genome-wide 30% abundance among 90% representatives as the first exact background artifact.
- Score per query and report Fisher exact p-values plus BH-FDR q-values.

## Phase 4: Falsification-First Agent Reasoning

Run evidence construction and falsification-first reasoning on individual strong-effect neighbor proteins:

- Add quiet external tool execution and trace logging.
- Add manifest-backed protein and DNA sequence lookup tools.
- Build candidate evidence packets from occurrence examples.
- Generate falsification checklists and rule-based status labels.
- Add a replayable LLM loop with centralized YAML prompt packs.
- Keep initial LLM actions limited to read-only evidence observations.
- Add a candidate-level multi-agent ledger workflow for literature grounding, hypothesis generation, evidence-needs derivation, tool planning, evidence audit, hypothesis revision, and synthesis.
- Add allowlisted literature retrieval, candidate-protein MMseqs, context/annotation summaries, and on-demand InterProScan evidence tools for team reasoning.
- Produce JSONL traces, per-candidate JSON ledgers, and Markdown evidence reports.

## Phase 5: Reporting and Evidence System

Build fuller reasoning and reporting outputs:

- Fuller cross-candidate evidence graph.
- Cross-candidate contradiction analysis.
- Tool execution trace.
- Optional deterministic annotation tool execution.
- Stronger evidence graph construction around the team workflow.
- Final report with accepted and rejected hypotheses.
