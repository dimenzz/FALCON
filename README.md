# FALCON

FALCON is a falsification-first metagenomic discovery system. The pipeline moves from seed proteins to candidate neighbor proteins through deterministic search and scoring, then runs one seed-aware reasoning runtime per candidate:

`seed/context evidence -> research notebook -> program planner -> step-local tool execution -> optional cohort investigation -> synthesis -> audit ledger`

The evidence graph is now an audit substrate, not the reasoning backbone.

## Install

```bash
uv sync
uv run pytest
uv run falcon --help
```

## Configuration

Configuration precedence is:

```text
CLI > YAML > defaults
```

Start from [configs/default.yaml](/mnt/data1/zhuwei/projects/FALCON/configs/default.yaml).

Relative paths inside YAML resolve against the config file's project root. CLI path overrides keep normal shell semantics.

Important agent keys:

- `agent.query_catalog`
- `agent.program_planner.max_rounds`
- `agent.program_planner.prompt_dir`
- `agent.program_planner.schema_retries`
- `agent.tools.manifest`
- `agent.reporting.ledger_dir`
- `agent.llm.mode`
- `agent.llm.model_name`

Removed keys such as `agent.workflow`, `agent.team.*`, and `agent.llm.prompt_pack` now fail fast with migration hints.

## Core CLI

Show effective config:

```bash
uv run falcon config show --config configs/default.yaml
```

Search homologs from FASTA seeds:

```bash
uv run falcon homology search \
  --query seeds.faa \
  --seed-metadata seeds.tsv \
  --config configs/default.yaml \
  --out-dir runs/example-search
```

Build occurrence cohorts:

```bash
uv run falcon cohort build \
  --hits runs/example-search/hits.jsonl \
  --config configs/default.yaml \
  --out-dir runs/example-search
```

Score co-localization:

```bash
uv run falcon colocation score \
  --cohort-contexts runs/example-search/cohort_contexts.jsonl \
  --background runs/background/background_30_abundance.json \
  --out-dir runs/example-search
```

Run candidate reasoning:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --query-catalog runs/example-search/seeds.jsonl \
  --config configs/default.yaml \
  --llm-mode live \
  --model-name your-model-name \
  --out-dir runs/example-agent
```

For local validation:

```bash
uv run falcon agent reason \
  --candidates runs/example-search/candidate_neighbors.jsonl \
  --query-catalog runs/example-search/seeds.jsonl \
  --config configs/default.yaml \
  --llm-mode mock \
  --out-dir runs/example-agent-mock
```

## Agent Runtime

The agent runtime is no longer split into deterministic / single / team workflows. There is one public reasoning path:

1. build `candidate_summary`, `seed_summary`, `candidate_neighbor_summary`, and `occurrence_bundle`
2. initialize a structured `ResearchNotebook`
3. ask the `ProgramPlanner` for a short agenda
4. execute one program step through allowlisted tools
5. update the notebook and audited ledger
6. optionally escalate to lightweight cohort analysis
7. synthesize a conservative supported claim and the next recommended program

The runtime keeps:

- `program_trace.jsonl`
- `tool_results.jsonl`
- `agent_events.jsonl`
- `ledgers/*.json`
- `reports/*.md`

External tool stdout/stderr stays in log files under `runtime.log_dir`.

## Current Scope

Implemented:

- YAML config + CLI overrides
- SQLite/manifest-backed data access
- FASTA seed parsing and `seeds.jsonl` query catalog
- MMseqs search and cohort/context construction
- co-localization scoring
- manifest-backed sequence lookup
- seed-aware program-driven candidate reasoning
- semantic bridge resolution
- lightweight cohort investigator primitives
- audit ledger and Markdown reports

Not implemented yet:

- richer structure-comparison tooling
- deeper cohort discovery programs beyond the current lightweight anomaly scans
