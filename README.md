# FALCON

FALCON is a falsification-first agentic system for metagenomic discovery. It is designed to move from seed proteins to candidate functional gene systems through a traceable loop:

1. find homologous proteins,
2. extract real genomic occurrences and their context,
3. calculate co-localization signals at cluster level,
4. run evidence-driven reasoning on individual candidate neighbor proteins,
5. report hypotheses, falsification attempts, contradictions, and uncertainty.

The current implementation is intentionally smaller than the full vision. It provides CLI-driven homology search, context cohort construction, co-localization scoring, sequence lookup, and Agent reasoning workflows ranging from deterministic rule-based reports to replayable single-LLM and multi-agent LLM review. The multi-agent workflow uses deterministic accession-based family naming, manifest-described tools, a per-candidate evidence graph, a role-specific context workbench, optional on-demand InterProScan/MMseqs checks, a generic local sequence architecture probe, scoped literature summaries, and controlled dynamic Python tools when explicitly enabled.

## Install

FALCON uses a Python `src/` layout and `uv` for environment management.

```bash
uv sync
```

For local development:

```bash
uv run pytest
uv run falcon --help
```

## Configuration

All runtime paths and scientific defaults are defined in YAML. Precedence is:

```text
CLI > YAML > defaults
```

Start from:

```bash
configs/default.yaml
```

The default config points to the current MGnify SQLite databases, manifests, MMseqs databases, and InterProScan installation.

Relative paths written inside a YAML config are resolved against the config file's project root, not against the shell directory where `falcon` is launched. For `configs/default.yaml`, FALCON finds the repository root and resolves paths such as `data/data_manifests/protein_manifest.csv`, `prompts/agent/team`, and `configs/tool_manifest.yaml` from there. This makes the default config safe to use from another working directory.

CLI path overrides keep normal shell semantics. For example, `--candidates relative/path.jsonl` and `--out-dir runs/test` are interpreted relative to your current working directory unless you pass absolute paths.

Run from outside the repository by using an absolute config path:

```bash
cd /tmp

uv run --project /mnt/data1/zhuwei/projects/FALCON falcon config show \
  --config /mnt/data1/zhuwei/projects/FALCON/configs/default.yaml
```

For a full run from another directory, prefer absolute input/output paths when referencing run artifacts:

```bash
cd /tmp

uv run --project /mnt/data1/zhuwei/projects/FALCON falcon agent reason \
  --candidates /mnt/data1/zhuwei/projects/FALCON/runs/example-search/candidate_neighbors.jsonl \
  --config /mnt/data1/zhuwei/projects/FALCON/configs/default.yaml \
  --out-dir /mnt/data1/zhuwei/projects/FALCON/runs/example-agent-team
```

## CLI

Show the effective configuration:

```bash
uv run falcon config show --config configs/default.yaml
```

Inspect configured data sources without running heavy scans:

```bash
uv run falcon inspect --config configs/default.yaml
```

Extract the context of a real protein occurrence using the default upstream/downstream CDS window:

```bash
uv run falcon context MGYG000321584_15_502_1218_- --config configs/default.yaml
```

Use a base-pair span instead:

```bash
uv run falcon context MGYG000321584_15_502_1218_- \
  --config configs/default.yaml \
  --window-mode bp \
  --bp-upstream 5000 \
  --bp-downstream 5000
```

`falcon context` v1 accepts a real occurrence-level `protein_id`. Cluster expansion is part of the architecture, but not the MVP command behavior.

Run homology search from a seed FASTA:

```bash
uv run falcon homology search \
  --query seeds.faa \
  --seed-metadata seeds.tsv \
  --config configs/default.yaml \
  --threads 16 \
  --out-dir runs/example-search
```

`seeds.tsv` is optional and uses two tab-separated columns:

```text
query_id	function_description
seed_1	ATP-dependent helicase seed
```

Build an occurrence-level context cohort from parsed homology hits:

```bash
uv run falcon cohort build \
  --hits runs/example-search/hits.jsonl \
  --config configs/default.yaml \
  --out-dir runs/example-search
```

Phase 2 treats context targets as 90% representative proteins. It does not expand to raw redundant members inside each 90% cluster.

MMseqs thread count is configured by `homology.threads` in YAML and can be overridden with `--threads`. InterProScan thread count is `tools.interproscan_threads`; team agent tool execution passes this value as `--cpu` when InterProScan is requested.

Build a 30% cluster abundance background:

```bash
uv run falcon background build \
  --config configs/default.yaml \
  --out-dir runs/background
```

Score co-localized neighbor clusters against the background:

```bash
uv run falcon colocation score \
  --cohort-contexts runs/example-search/cohort_contexts.jsonl \
  --background runs/background/background_30_abundance.json \
  --out-dir runs/example-search
```

The colocation scorer works per query, excludes the target's own 30% cluster, uses per-context presence as the main count, emits copy counts as supporting evidence, and writes ranked candidate neighbor clusters with example proteins.

`candidate_neighbors.jsonl` and `candidate_neighbors.tsv` are exploration-first queues. The default thresholds require at least 3 supporting contexts, presence rate >= 0.01, fold enrichment >= 2, and q-value <= 0.05, then keep the top 100 candidates by presence contexts. Use `--max-candidates 0` to disable candidate truncation.

Read a protein sequence through the manifest-backed sequence layer:

```bash
uv run falcon sequence protein \
  --protein-id MGYG000321584_15_502_1218_- \
  --config configs/default.yaml
```

Read the DNA span for a protein occurrence. Negative-strand proteins are returned in protein orientation by default, while original coordinates remain in the JSON output:

```bash
uv run falcon sequence dna \
  --protein-id MGYG000321584_15_502_1218_- \
  --flank-bp 100 \
  --config configs/default.yaml
```

Run the deterministic Agent MVP over candidate neighbor clusters:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --out-dir runs/example-agent
```

The Agent MVP reads occurrence examples, hydrates them with SQLite annotations and cluster mappings, checks sequence availability, writes `agent_results.jsonl`, and renders per-candidate Markdown reports. It records uncertainty instead of inventing conclusions when evidence is missing.

Run the LLM-backed falsification loop with a mock provider:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --llm-mode mock \
  --out-dir runs/example-agent-llm-mock
```

Run the live OpenAI-compatible Chat Completions provider:

```bash
export OPENAI_API_KEY=...

uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --llm-mode live \
  --model-name your-model-name \
  --base-url https://api.openai.com/v1 \
  --max-iterations 6 \
  --out-dir runs/example-agent-live
```

Run the team workflow with manifest-driven tools and progress logging:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --agent-workflow team \
  --llm-mode live \
  --model-name your-model-name \
  --out-dir runs/example-agent-team
```

Dynamic tools are off by default. When enabled, the LLM may design a read-only Python script for a local evidence need that fixed tools cannot answer. FALCON reviews the script, runs it in an outer Python subprocess, captures logs, and stores script/input/output artifacts under `dynamic_tools/`.

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --agent-workflow team \
  --llm-mode live \
  --model-name your-model-name \
  --dynamic-tools \
  --dynamic-tool-timeout 60 \
  --out-dir runs/example-agent-team-dynamic
```

Live mode requires an explicit model name from YAML or `--model-name`; FALCON does not guess a default model. Custom OpenAI-compatible endpoints are supported through `agent.llm.base_url` or `--base-url`. API key lookup uses `agent.llm.api_key_env`, defaulting to `OPENAI_API_KEY`.

LLM prompts are centralized under `prompts/agent/`. The default prompt pack is `prompts/agent/falsification_loop.yaml` and defines the allowed JSON actions:

- `propose_hypothesis`
- `request_context_summary`
- `request_sequence_summary`
- `compare_example_annotations`
- `record_contradiction`
- `finalize`

The single-agent LLM loop only exposes read-only evidence already collected by FALCON: candidate statistics, occurrence-level genomic context, sequence availability, and SQLite annotations. It writes `agent_trace.jsonl` and `llm_calls.jsonl` for replay and audit. For backward compatibility, setting `--llm-mode mock|live|replay` without `--agent-workflow` runs this single-agent workflow.

Run the candidate-level multi-agent workflow:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --config configs/default.yaml \
  --agent-workflow team \
  --llm-mode live \
  --model-name your-model-name \
  --base-url http://your-openai-compatible-endpoint/v1 \
  --max-team-rounds 2 \
  --team-prompt-dir prompts/agent/team \
  --tool-manifest configs/tool_manifest.yaml \
  --progress \
  --literature-max-results 5 \
  --agent-mmseqs-max-hits 25 \
  --out-dir runs/example-agent-team
```

The team workflow now uses a per-candidate evidence graph ledger. Each role receives a structured context pack with a `context_workbench`: deterministic family naming, occurrence examples, scoped literature priors, current graph state, unresolved gaps, the manifest-derived tool catalog, data contracts, artifact index, and dynamic tool contract. The `tool_planner` selects tools from the workbench rather than prompt-embedded tool names, and FALCON validates each plan against manifest capabilities before execution. Literature search aggregates Europe PMC and PubMed records and de-duplicates by PMID, DOI, then title. InterProScan, candidate MMseqs, the local sequence architecture probe, full-context feature queries, motif checks, and optional dynamic Python tools are recorded with auditable reasons, logs, raw observations, summary nodes, and evidence graph edges.

Team workflow artifacts include:

- `agent_team_trace.jsonl`
- `agent_events.jsonl`
- `tool_plan.jsonl`
- `tool_results.jsonl`
- `literature_evidence.jsonl`
- `ledgers/*.json` with `evidence_graph`

External tool stdout and stderr are captured under `runtime.log_dir`. When `runtime.progress` is true, long-running tools also emit CLI stderr progress events and heartbeat messages while preserving machine-readable JSON on stdout. The run directory records the same lifecycle events in `agent_events.jsonl`. Live accession enrichment for `COG`, `KEGG`, `Pfam`, and `InterPro` is cached immutably under `runtime.cache_dir/accession/`.

## Current Scope

Implemented in the MVP:

- Typer CLI entry point.
- YAML config loading and CLI override merging.
- SQLite and manifest inspection.
- Occurrence-level context extraction from `proteins.db`.
- Optional cluster annotations in context output.
- MMseqs homology search wrapper for FASTA seeds.
- Seed metadata parsing from FASTA headers and optional TSV files.
- Homology hit JSONL artifacts.
- 90% representative context cohort construction.
- Configurable thread count for MMseqs and InterProScan tool adapters.
- Genome-wide exact 30% cluster abundance background artifacts.
- Per-query co-localization scoring with Fisher exact p-values and BH-FDR q-values.
- Manifest-backed protein and DNA sequence lookup.
- Quiet external tool execution with stdout/stderr log artifacts.
- Deterministic Agent MVP evidence packets and Markdown reports.
- LLM-backed, replayable Agent loop over read-only evidence using OpenAI-compatible Chat Completions.
- Candidate-level multi-agent evidence-graph workflow with literature grounding, hypothesis generation, evidence-needs derivation, tool planning, evidence audit, hypothesis revision, and synthesis roles.
- On-demand InterProScan tool execution in the team workflow.
- Candidate-protein MMseqs tool execution in the team workflow.
- YAML tool manifest with cost-aware tool planning.
- Runtime progress and JSONL event logs for long-running agent tools.
- Europe PMC + PubMed literature evidence aggregation for team reasoning.
- Centralized YAML prompt packs under `prompts/agent/`.
- Fixture-based tests that do not require the large NFS databases.

Not implemented yet:

- Dynamic tool generation.
- Cross-candidate evidence graph database.
