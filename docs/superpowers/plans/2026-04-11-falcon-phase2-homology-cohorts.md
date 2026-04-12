# FALCON Phase 2 Homology and Cohorts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FASTA-based MMseqs homology search and 90% representative context cohort construction.

**Architecture:** Keep seed parsing, MMseqs execution, hit parsing, and cohort construction in focused modules. Keep CLI commands as thin orchestration around these modules and preserve the cluster-vs-occurrence boundary.

**Tech Stack:** Python 3.11+, Typer, PyYAML, sqlite3, pytest, MMseqs easy-search.

---

### Task 1: Seed and Homology Artifacts

**Files:**
- Create: `src/falcon/homology/seeds.py`
- Create: `src/falcon/homology/search.py`
- Test: `tests/test_seeds.py`
- Test: `tests/test_homology.py`

- [ ] Add tests for multi-FASTA parsing, seed metadata override, MMseqs TSV parsing, and fake MMseqs invocation.
- [ ] Implement seed records, metadata loading, hit records, raw TSV parsing, and JSONL writing.
- [ ] Verify with `uv run pytest tests/test_seeds.py tests/test_homology.py`.

### Task 2: Cohort Builder

**Files:**
- Create: `src/falcon/cohort/__init__.py`
- Create: `src/falcon/cohort/builder.py`
- Modify: `src/falcon/data/clusters.py`
- Test: `tests/test_cohort.py`

- [ ] Add tests for 90% direct cohorts, 30% to 90% expansion, and optional 90% to sibling 30% expansion.
- [ ] Implement cluster lookup helpers and deduplicated context cohort output.
- [ ] Verify with `uv run pytest tests/test_cohort.py`.

### Task 3: CLI and Config

**Files:**
- Modify: `src/falcon/cli.py`
- Modify: `src/falcon/config.py`
- Modify: `configs/default.yaml`
- Test: `tests/test_cli.py`

- [ ] Add tests for `falcon homology search` and `falcon cohort build` using fake MMseqs and fixture SQLite databases.
- [ ] Add homology defaults and CLI commands.
- [ ] Pass configured MMseqs threads as `--threads`; preserve InterProScan threads as `--cpu` in the tool adapter.
- [ ] Verify with `uv run pytest tests/test_cli.py`.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data_model.md`
- Modify: `docs/development_plan.md`

- [ ] Document Phase 2 commands, artifacts, and the 90% representative cohort policy.
- [ ] Run `uv run pytest`.
- [ ] Run CLI help smoke commands for `falcon homology search` and `falcon cohort build`.
