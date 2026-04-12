# FALCON Data Model

## proteins.db

`proteins.db` contains real occurrence-level protein rows. The MVP uses the `proteins` table for context extraction.

Important columns:

- `protein_id`
- `contig_id`
- `mag_id`
- `start`
- `end`
- `strand`
- `length`
- `product`
- `gene_name`
- `locus_tag`
- `pfam`
- `interpro`
- `kegg`
- `cog_category`
- `cog_id`
- `ec_number`
- `eggnog`

`contigs` provides contig metadata such as length, taxonomy, and environment.

## clusters.db

`clusters.db` contains cluster membership:

- `representative_id`
- `member_id`
- `cluster_level`

The known levels are 90 and 30. FALCON should use this database for homology grouping, redundancy reduction, and future cluster-level statistics.

## Manifests and Sequences

The SQLite databases do not contain DNA or protein sequences. FASTA paths are resolved through two-column CSV manifests:

- `data/data_manifests/genome_manifest.csv`
- `data/data_manifests/protein_manifest.csv`

Path resolution belongs in the data access layer. Other modules should not parse these manifests directly.

## Cluster Expansion Semantics

Future homology/statistics behavior should follow these rules:

- If homology search uses the 30% database, extract occurrence contexts for all corresponding 90% representative members before computing statistics.
- If homology search uses the 90% database, provide an option to expand to sibling 90% representatives within the same 30% cluster.
- Co-localization statistics should aggregate neighbor proteins into 30% clusters.
- Agent reasoning should use real occurrence examples, not cluster representatives alone.

The Phase 2 cohort builder does not expand from 90% representatives to raw redundant members at `cluster_level=90`.

## Homology Artifacts

`falcon homology search` writes:

- `raw_hits.tsv`: MMseqs output with fixed parse columns.
- `hits.jsonl`: parsed hits with query ID, target ID, alignment metrics, search level, and rank.
- `seeds.jsonl`: parsed seed records with FASTA header descriptions and optional TSV function descriptions.
- `summary.json`: run metadata and warnings.

`falcon cohort build` writes:

- `cohort_members.jsonl`: deduplicated 90% representatives and their supporting hits.
- `cohort_contexts.jsonl`: occurrence-level context for each 90% representative target.
- `cohort_summary.json`: cohort counts and output paths.

`falcon background build` writes:

- `background_30_abundance.json`: 30% cluster abundance among 90% representatives.
- `background_30_abundance.tsv`: tabular view of the same counts.

`falcon colocation score` writes:

- `colocation_stats.jsonl`: per-query neighbor 30% cluster statistics.
- `candidate_neighbors.jsonl`: filtered ranked candidates with examples.
- `candidate_neighbors.tsv`: tabular candidate summary.
- `colocation_summary.json`: counts and output paths.

`falcon sequence protein` returns manifest-backed protein FASTA records by occurrence `protein_id`.

`falcon sequence dna` returns manifest-backed DNA sequence around a protein occurrence. Coordinates are 1-based inclusive in the JSON output. Negative-strand proteins are returned in protein orientation by default, using reverse complement sequence while retaining the original genomic coordinate span.

`falcon agent reason` writes:

- `agent_results.jsonl`: one deterministic evidence and reasoning record per candidate neighbor cluster.
- `reports/*.md`: one Markdown evidence report per candidate.
- `agent_summary.json`: counts and output paths.

Agent evidence packets hydrate Phase 3 candidate examples with real occurrence annotations, cluster mappings, context windows, and sequence availability. Missing sequence or annotation evidence is recorded as uncertainty instead of being guessed.

## Tool Resources

MMseqs supports `--threads`; FALCON maps this from `homology.threads`. InterProScan supports `--cpu`; FALCON maps this from `tools.interproscan_threads` in its tool adapter layer.

External command stdout and stderr are captured to log files under `runtime.log_dir`. Homology summaries include a tool trace with command, return code, timestamps, and log paths.
