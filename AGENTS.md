# FALCON Development Constraints

FALCON is a falsification-first metagenomic discovery system. Development should preserve the scientific separation between deterministic data extraction, statistical signal discovery, and agent reasoning.

## Core Rules

- Keep cluster-level statistics separate from occurrence-level evidence.
- Treat `proteins.db` occurrence rows as the canonical source for genomic context and annotations.
- Treat `clusters.db` as the canonical source for 90% and 30% cluster membership.
- Do not scatter FASTA path parsing across modules; sequence access must go through the manifest/sequence data layer.
- Keep deterministic data extraction separate from LLM reasoning. The LLM loop may consume structured evidence packets and request fixed allowlisted tools through the tool registry; it must not execute arbitrary shell commands.
- Keep the YAML tool manifest and Python tool registry synchronized. Tool ids in prompts, plans, ledgers, and tool observations must come from the manifest; do not hard-code tool preferences in role prompts.
- Keep agent prompts centralized under `prompts/agent/`; do not scatter prompt text across CLI or data modules.
- Do not add dynamic tool generation or heavy external tool orchestration without a new design pass.
- Do not make claims without provenance. Future reports must link conclusions to raw observations, tool calls, and reasoning steps.

## MVP Boundaries

- CLI first.
- YAML configuration only.
- Config precedence must remain `CLI > YAML > defaults`.
- Context extraction v1 accepts occurrence-level protein IDs.
- Routine tests must use small fixtures; large NFS databases are for manual smoke checks unless a test is explicitly marked otherwise.
- Phase 2 homology input is FASTA only; do not add protein-ID seed extraction without a new design pass.
- Phase 2 context cohorts should use 90% representative proteins as context targets and should not expand to raw redundant members inside the 90% cluster.
- External tool stdout/stderr should be captured to log files, not mixed into normal CLI JSON output.
- Sequence access should go through the manifest-backed sequence layer.
- Live LLM mode must require an explicit `agent.llm.model_name` from YAML or CLI. Do not guess a default model.
- LLM loop actions must remain allowlisted and auditable through trace artifacts and per-candidate ledgers.
- Team workflow prompts should consume structured context packs and evidence graph slices. Do not fall back to dumping raw ledgers or writing role-specific prompt text in orchestration code.
- Runtime progress events should go to stderr and `agent_events.jsonl`; external tool stdout/stderr must remain in tool log files.

## Cluster Semantics

- Homology search may use either 90% or 30% MMseqs databases.
- If 30% search is used, downstream statistics should extract contexts for all relevant 90% members.
- If 90% search is used, a later option may expand to the sibling members inside the same 30% cluster.
- Co-localization statistics should merge neighbor proteins to 30% clusters.
- Agent reasoning should operate on individual strong-effect neighbor proteins and real occurrence examples, not abstract neighborhood aggregates alone.
