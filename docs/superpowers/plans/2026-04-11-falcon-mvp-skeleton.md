# FALCON MVP Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable CLI MVP with YAML config loading, data-source inspection, and occurrence-level context extraction.

**Architecture:** Use a small layered Python package under `src/falcon`. Keep CLI, config merging, SQLite/manifest repositories, and context extraction separate. Reserve later scientific layers without implementing homology, co-localization, or agent reasoning.

**Tech Stack:** Python 3.11+, uv, Typer, PyYAML, sqlite3, pytest.

---

### Task 1: Project Docs and Metadata

**Files:**
- Modify: `README.md`
- Create: `AGENTS.md`
- Create: `pyproject.toml`
- Create: `configs/default.yaml`
- Create: `docs/architecture.md`
- Create: `docs/data_model.md`
- Create: `docs/development_plan.md`
- Create: `docs/superpowers/specs/2026-04-11-falcon-mvp-skeleton-design.md`

- [ ] Write the project overview, development constraints, uv project metadata, and default YAML config.
- [ ] Keep documentation English-first and state MVP limitations explicitly.

### Task 2: Test-First Behavioral Coverage

**Files:**
- Create: `tests/test_config.py`
- Create: `tests/test_manifests.py`
- Create: `tests/test_context.py`
- Create: `tests/test_cli.py`

- [ ] Write tests for config precedence.
- [ ] Write tests for manifest parsing.
- [ ] Write fixture SQLite tests for gene-window and bp-span context extraction.
- [ ] Write CLI tests for `config show`, `inspect`, and `context`.
- [ ] Run `pytest` and confirm failures are caused by missing implementation.

### Task 3: Minimal Package Implementation

**Files:**
- Create: `src/falcon/__init__.py`
- Create: `src/falcon/config.py`
- Create: `src/falcon/cli.py`
- Create: `src/falcon/data/manifests.py`
- Create: `src/falcon/data/sqlite.py`
- Create: `src/falcon/data/proteins.py`
- Create: `src/falcon/data/clusters.py`
- Create: `src/falcon/context/extractor.py`
- Create minimal package files for reserved layers.

- [ ] Implement config defaults, YAML loading, and deep CLI override merging.
- [ ] Implement manifest loading through the data layer.
- [ ] Implement read-only SQLite helpers and protein/cluster repositories.
- [ ] Implement occurrence-only context extraction for gene-window and bp-span modes.
- [ ] Implement Typer CLI commands and JSON output.

### Task 4: Verification

**Files:**
- Modify as needed based on test failures.
- Create: `sandbox/.gitkeep`
- Create: `cache/.gitkeep`
- Create: `logs/.gitkeep`

- [ ] Run the full test suite with `uv run pytest`.
- [ ] Run smoke commands for `falcon --help`, `falcon config show`, and fixture-backed CLI behavior.
- [ ] Run `uv lock` to produce `uv.lock`.
- [ ] Review `git status` and `git diff`.
