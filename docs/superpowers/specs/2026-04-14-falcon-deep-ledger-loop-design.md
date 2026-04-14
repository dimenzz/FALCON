# FALCON Deep Multi-Agent Ledger Loop Design

## Summary

Upgrade the `team` workflow from a shallow role chain to a per-candidate ledger loop. The loop grounds each candidate in literature before hypothesis generation, derives hypothesis-specific falsification tests, plans fixed allowlisted tools, audits collected evidence, revises hypotheses, and synthesizes a conservative conclusion from the ledger.

## Design

The team workflow uses dedicated role modules:

- `literature_scout`
- `hypothesis_generator`
- `evidence_needs`
- `tool_planner`
- `evidence_auditor`
- `hypothesis_reviser`
- `synthesizer`

Each candidate writes a JSON ledger with candidate evidence, deterministic checks, literature records, literature brief, hypotheses, falsification tests, evidence needs, tool plan, tool observations, audit findings, revisions, contradiction ledger, and final synthesis.

Tool execution stays fixed and allowlisted through the existing `src/falcon/tools` area. The first registry tools are `search_literature`, `inspect_context`, `summarize_annotations`, `run_interproscan`, and `run_candidate_mmseqs`.

## Validation

Role outputs are pydantic-validated. Invalid JSON, invalid tool names, or missing required fields trigger schema retries. Exhausted retries mark the candidate ledger as blocked rather than silently accepting malformed reasoning.

## Scope

This phase does not add dynamic tool generation, arbitrary shell execution, or cross-candidate system synthesis. The reasoning object remains one strong-effect candidate neighbor protein at a time.
