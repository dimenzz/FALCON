# FALCON Phase 3 Co-Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact 30% cluster abundance background artifacts and per-query co-localization candidate scoring.

**Architecture:** Keep background building and colocation scoring in focused `falcon.colocation` modules. Keep CLI commands thin and artifact-oriented.

**Tech Stack:** Python 3.11+, Typer, PyYAML, sqlite3, SciPy, pytest.

---

### Task 1: Background Builder

**Files:**
- Create: `src/falcon/colocation/background.py`
- Test: `tests/test_background.py`

- [ ] Add fixture `clusters.db` tests for 30% abundance over 90% representatives.
- [ ] Implement JSON and TSV background artifacts.
- [ ] Verify with `uv run pytest tests/test_background.py`.

### Task 2: Colocation Scorer

**Files:**
- Create: `src/falcon/colocation/scoring.py`
- Test: `tests/test_colocation.py`

- [ ] Add tests for per-query assignment, self-cluster exclusion, presence/copy counts, Fisher p-values, BH-FDR q-values, and example limits.
- [ ] Implement scoring and candidate filtering.
- [ ] Verify with `uv run pytest tests/test_colocation.py`.

### Task 3: CLI, Config, and Dependencies

**Files:**
- Modify: `src/falcon/cli.py`
- Modify: `src/falcon/config.py`
- Modify: `configs/default.yaml`
- Modify: `pyproject.toml`
- Test: `tests/test_cli.py`

- [ ] Add SciPy dependency.
- [ ] Add background and colocation config defaults.
- [ ] Add `falcon background build` and `falcon colocation score`.
- [ ] Verify with `uv run pytest tests/test_cli.py`.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data_model.md`
- Modify: `docs/development_plan.md`

- [ ] Document Phase 3 commands and artifacts.
- [ ] Run `uv lock`.
- [ ] Run `uv run pytest`.
- [ ] Run CLI help smoke commands.
