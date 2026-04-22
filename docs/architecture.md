# FALCON Architecture

## Pipeline Boundary

FALCON keeps three scientific layers separate:

1. deterministic data extraction
2. statistical signal discovery
3. agent reasoning

Cluster-level statistics stay separate from occurrence-level evidence. `proteins.db` remains the canonical occurrence source. `clusters.db` remains the canonical cluster source.

## Current Runtime

The reasoning side now has one public runtime:

`candidate evidence -> notebook -> program planner -> step-local tool planning -> execution -> notebook update -> optional cohort investigator -> synthesis -> audit ledger`

### Front-stage reasoning

- `ResearchNotebook`
  - anomalies
  - failed bridges
  - competing explanations
  - escalation signals
  - recent outcomes

- `ProgramPlanner`
  - emits a short 1-4 step research agenda
  - replans after each completed step
  - chooses programs such as:
    - `identity_adjudication`
    - `semantic_bridge_resolution`
    - `local_context_discrimination`
    - `cohort_anomaly_scan`
    - `subgroup_comparison`
    - `defer_unresolved`

- `Tool planner`
  - no longer owns the whole loop
  - only routes tools inside the active program step

- `Cohort investigator`
  - optional escalation path
  - currently provides lightweight length-shift and co-variation primitives

### Back-stage audit

The evidence graph is no longer the reasoning backbone. It is an audit ledger for executed facts only:

- `tool_run`
- `raw_observation`
- `normalized_summary`
- `audited_claim`
- `contradiction`
- `final_supported_claim`

Weak graph edges are sufficient:

- `produced_by`
- `derived_from`
- `supports`
- `contradicts`
- `refers_to`

## Seed-aware inputs

Reasoning now takes four explicit inputs:

- `candidate_summary`
- `seed_summary`
- `candidate_neighbor_summary`
- `occurrence_bundle`

`seed_summary` includes:

- query prior from FASTA header / metadata TSV
- target consensus annotation aggregated from occurrence examples

The query prior is a soft prior only. It can guide planning and literature framing, but it is not direct evidence for the candidate claim.

## Tooling

Tools remain manifest-described and allowlisted. Key built-in capabilities:

- literature search
- context inspection / annotation summaries
- context feature queries
- InterProScan
- candidate MMseqs
- semantic bridge resolution
- local sequence architecture probe

External tool stdout/stderr is captured to log files, while progress events go to stderr and `agent_events.jsonl`.
