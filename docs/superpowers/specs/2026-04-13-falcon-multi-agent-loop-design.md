# FALCON Multi-Agent Loop Design

Superseded by `docs/superpowers/specs/2026-04-14-falcon-deep-ledger-loop-design.md`.

## Summary

Upgrade agent reasoning from a shallow single-LLM action loop to a candidate-level multi-agent review workflow. The workflow keeps the project boundary that each agent run reasons over one strong co-localized neighbor protein, but expands LLM participation into hypothesis generation, tool planning, evidence review, criticism, revision, and final synthesis.

## Design

The new `team` workflow runs independent role calls:

- `hypothesis`: generate falsifiable candidate hypotheses.
- `tool_planner`: request allowlisted evidence tools.
- `evidence_reviewer`: interpret tool outputs and revise hypotheses.
- `critic`: identify contradictions, overclaims, and missing evidence.
- `synthesizer`: produce final conclusion and uncertainty.

The loop is bounded by `agent.team.max_rounds`. If the critic does not approve within the limit, the result remains conservative.

Tool execution is deterministic and allowlisted. The first tool set includes read-only evidence summaries, Europe PMC + PubMed literature search, and on-demand InterProScan domain checks. InterProScan is skipped when existing PFAM/InterPro annotations are sufficient unless the planner explicitly forces a domain double-check.

## Artifacts

Team runs write:

- `agent_team_trace.jsonl`
- `tool_plan.jsonl`
- `tool_results.jsonl`
- `literature_evidence.jsonl`
- per-candidate Markdown reports with a Multi-Agent Review section.

## Scope

The workflow does not add dynamic tool generation or arbitrary shell execution. Deterministic and single-agent workflows remain available for short-term comparison, but `team` is the intended direction.
# Superseded

This design is superseded by the 2026-04-21 research-runtime refactor plan and no longer describes the current agent runtime.
