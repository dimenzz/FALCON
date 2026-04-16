# FALCON Candidate Reasoning Backbone Refactor

## Summary

Refactor the candidate-level team workflow into a deterministic-first backbone:

`accession enrichment -> deterministic family selector -> scoped literature summaries -> family+context hypothesis templates -> falsification tests / evidence needs -> tool planning by evidence gap -> raw observation + tool summary -> audit -> revision -> final synthesis`

Execution starts from baseline commit `3329e28`.

## Key Changes

- Add accession enrichment adapters for `COG`, `KEGG`, `Pfam`, and `InterPro`, all using `Live+Cache` with immutable cache under `runtime.cache_dir`.
- Front-load deterministic family naming and keep `supported claim` capped at `family + system role`.
- Replace candidate-global literature briefing with structured `family prior`, `system prior`, and `mechanism caution` summaries.
- Replace freeform hypothesis generation with `1 main + 1 competing` structured hypotheses from `family + context` templates.
- Rewire the evidence graph around:
  `hypothesis -> falsification_test -> evidence_need -> tool_request -> raw_observation -> tool_summary -> audit_finding`
- Require every fixed tool to emit both raw observations and deterministic tool summaries with workflow-managed lifecycle.
- Add a generic local sequence architecture probe that reports repeat-structure facts and boolean/count summaries.
- Tighten existing tool contracts so MMseqs and InterPro outputs cannot be overstated.
- Update final reporting to three sections:
  - `supported claim`
  - `working mechanistic hypotheses`
  - `next evidence collection plan`

## Tests

- Add unit coverage for accession enrichment, deterministic family selection, summary lifecycle, graph wiring, local architecture probing, and report rendering.
- Re-run the team workflow tests against the new backbone.
- Re-run focused Cas9 regressions to ensure:
  - PF09711-family cases do not drift between `hypothetical protein` and named family labels.
  - MMseqs summaries do not imply named function beyond the hit-table contract.
  - InterPro-derived architecture facts enter the evidence chain as structured facts.

## Assumptions

- Accessions are enriched live on first use and then cached immutably.
- Dynamic tools remain opt-in and outside the core loop for this refactor.
- Residue/motif reasoning remains de-emphasized until stronger structure-aware tooling exists.
