# FALCON Phase 4 Agent Evidence and Tool Logging Plan

> **For agentic workers:** implement with TDD and verify each task before moving on.

**Goal:** Add quiet external tool logging, manifest-backed sequence lookup, and deterministic Agent MVP evidence reports.

## Task 1: Tool Runner and MMseqs Logging

- Add a shared external command runner that captures stdout/stderr to log files and returns a structured trace.
- Route MMseqs search through the runner.
- Include `tool_trace` in homology summaries.
- Test stdout/stderr capture and failure log paths.

## Task 2: Sequence Access

- Add a manifest-backed sequence repository.
- Support protein sequence lookup by occurrence `protein_id`.
- Support DNA lookup by occurrence `protein_id` with flank and max-bases guard.
- Return negative-strand DNA in protein orientation by default.
- Add sequence CLI commands and fixture tests.

## Task 3: Agent Evidence MVP

- Add `falcon agent reason` for batch candidate JSONL input.
- Hydrate candidate examples with occurrence annotations, cluster mappings, context windows, and sequence availability.
- Generate deterministic falsification checklists and support status labels.
- Write `agent_results.jsonl`, `agent_summary.json`, and Markdown reports.

## Task 4: Documentation and Verification

- Document new commands, outputs, and non-goals.
- Run targeted tests, full test suite, compileall, and CLI smoke checks.
