# FALCON

FALCON is a falsification-first agentic system for metagenomic discovery. It is designed to move from seed proteins to candidate functional gene systems through a traceable loop:

1. find homologous proteins,
2. extract real genomic occurrences and their context,
3. calculate co-localization signals at cluster level,
4. run evidence-driven reasoning on individual candidate neighbor proteins,
5. report hypotheses, falsification attempts, contradictions, and uncertainty.

The current implementation is intentionally smaller than the full vision. It provides CLI-driven homology search, context cohort construction, co-localization scoring, sequence lookup, and a deterministic Agent MVP that produces auditable evidence packets and reports. It does not yet run LLM reasoning, InterProScan execution, dynamic tool generation, or full evidence graph assembly.

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

MMseqs thread count is configured by `homology.threads` in YAML and can be overridden with `--threads`. InterProScan is not executed yet, but its configured thread count is `tools.interproscan_threads`; future InterProScan commands should pass this value as `--cpu`.

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

External tool logs are quiet by default. MMseqs stdout and stderr are captured under `runtime.log_dir`, and successful homology summaries include a `tool_trace` with log paths. If MMseqs fails, the CLI reports the exit code and the captured log paths.

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
- Fixture-based tests that do not require the large NFS databases.

Not implemented yet:

- LLM-backed agent reasoning.
- Automatic InterProScan execution.
- Dynamic tool generation.
- Full evidence graph and final discovery reports.
