# FALCON Research Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current multi-workflow agent layer with one seed-aware, program-driven reasoning runtime and slim the repository to match that single supported design.

**Architecture:** Keep the upstream homology, context, cohort, and colocation pipeline intact, but replace the current agent workflow split with a single runtime built around a research notebook, a program planner, step-local tool routing, optional cohort investigation, and an audit ledger. Evidence graph remains only as a provenance substrate for executed facts and audited outputs.

**Tech Stack:** Python, Typer, Pydantic, YAML config, pytest, existing SQLite/manifest access layer, existing tool runners.

---

## Target File Structure

- `src/falcon/reasoning/`
  - New runtime entrypoint, notebook, agenda/program types, planner orchestration, cohort investigator
- `src/falcon/evidence/`
  - Audit-ledger state, event compilation, raw/summary/audited artifact wiring
- `src/falcon/tools/`
  - Keep tool runners, add semantic bridge and cohort primitives, remove old runtime-coupled assumptions
- `src/falcon/cli.py`
  - Keep `falcon agent reason`, remove old workflow/single-agent flags, require `query_catalog`
- `src/falcon/config.py`
  - Replace old `agent.workflow` / `agent.team.*` layout with the new runtime-focused config
- `src/falcon/reporting/markdown.py`
  - Render notebook/program-driven reports instead of old hypothesis/test graph reports
- `docs/`
  - Rewrite current docs to match the new runtime and mark old backbone docs superseded
- `tests/`
  - Replace workflow-era tests with notebook/program runtime, migration error, and regression coverage

## Execution Tasks

### Task 1: Lock the runtime contract and seed-aware inputs

**Files:**
- Create: `src/falcon/reasoning/types.py`
- Create: `src/falcon/reasoning/notebook.py`
- Create: `src/falcon/reasoning/query_catalog.py`
- Modify: `src/falcon/agent/reasoning.py`
- Test: `tests/test_reasoning_runtime.py`

- [ ] Add tests for `query_catalog`-required input, `seed_summary` construction, and seed prior semantics.
- [ ] Introduce explicit runtime objects for `candidate_summary`, `seed_summary`, `candidate_neighbor_summary`, and `occurrence_bundle`.
- [ ] Move seed aggregation logic out of ad hoc candidate evidence packing and into a dedicated query-catalog loader.
- [ ] Verify the new tests pass.
- [ ] Commit.

### Task 2: Build notebook + agenda runtime and demote graph

**Files:**
- Create: `src/falcon/reasoning/runtime.py`
- Create: `src/falcon/reasoning/programs.py`
- Create: `src/falcon/evidence/ledger.py`
- Modify: `src/falcon/agent/team/*` or remove/rehome replaced files
- Test: `tests/test_reasoning_runtime.py`
- Test: `tests/test_audit_ledger.py`

- [ ] Add failing tests for notebook updates, agenda generation, step-by-step replanning, and audit-ledger-only graph contents.
- [ ] Implement `ResearchNotebook`, `ResearchAgenda`, `ProgramStep`, and runtime orchestration.
- [ ] Restrict graph/ledger outputs to executed facts and audited claims.
- [ ] Verify tests pass.
- [ ] Commit.

### Task 3: Add semantic bridge and cohort primitives

**Files:**
- Create: `src/falcon/tools/semantic_bridge.py`
- Create: `src/falcon/reasoning/cohort_investigator.py`
- Modify: `src/falcon/tools/agent_registry.py`
- Test: `tests/test_semantic_bridge.py`
- Test: `tests/test_cohort_investigator.py`

- [ ] Add failing tests for PF04851-style bridge resolution, size-shift scans, neighbor co-variation, and subgroup comparison outputs.
- [ ] Implement semantic bridge resolution and cohort investigator v1 primitives.
- [ ] Wire them into program-step execution and notebook escalation signals.
- [ ] Verify tests pass.
- [ ] Commit.

### Task 4: Remove old workflows and shrink CLI/config

**Files:**
- Modify: `src/falcon/cli.py`
- Modify: `src/falcon/config.py`
- Delete: `src/falcon/agent/loop.py`
- Delete: `src/falcon/agent/actions.py`
- Delete: `src/falcon/agent/prompts.py`
- Delete: `prompts/agent/falsification_loop.yaml`
- Test: `tests/test_cli.py`
- Test: `tests/test_config.py`

- [ ] Add failing tests for migration errors on removed CLI flags and YAML keys.
- [ ] Remove old deterministic/single-agent workflow code paths and shrink `falcon agent reason` to the new runtime.
- [ ] Add migration-hint errors for removed parameters and config keys.
- [ ] Verify tests pass.
- [ ] Commit.

### Task 5: Rewrite reports, docs, and regressions

**Files:**
- Modify: `src/falcon/reporting/markdown.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/llm_agent.md`
- Modify: old spec/plan docs to mark them superseded
- Test: `tests/test_reporting_markdown.py`
- Test: `tests/test_agent_reasoning_regressions.py`

- [ ] Add failing tests covering the Cas9 literature-failure case, RM semantic-bridge case, and distinct agenda paths across Cas9/RM/TA.
- [ ] Rewrite report rendering around notebook/program/audited outputs.
- [ ] Update current docs and explicitly supersede old backbone docs.
- [ ] Verify tests pass.
- [ ] Commit.

### Task 6: Final verification and integration

**Files:**
- Modify: `/mnt/data1/zhuwei/projects/FALCON` worktree sync targets

- [ ] Run the full test suite and `git diff --check`.
- [ ] Commit the final worktree state.
- [ ] Sync the final tree back into `/mnt/data1/zhuwei/projects/FALCON`, preserving the user’s uncommitted `configs/default.yaml` base_url change.
- [ ] Re-run the full test suite in the main workspace.
- [ ] Commit in the main workspace or leave staged per user preference.
