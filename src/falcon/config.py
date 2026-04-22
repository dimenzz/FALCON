from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "data": {
        "proteins_db": "/mnt/nfs/share/MGnify/all_data/proteins.db",
        "clusters_db": "/mnt/nfs/share/MGnify/all_data/clusters.db",
        "genome_manifest": "data/data_manifests/genome_manifest.csv",
        "protein_manifest": "data/data_manifests/protein_manifest.csv",
        "mmseqs_db_root": "/mnt/nfs/share/MGnify/all_data/mmseqs_db",
    },
    "tools": {
        "mmseqs": "/mnt/data1/zhuwei/software/mmseqs/bin/mmseqs",
        "interproscan": "/mnt/data1/zhuwei/software/interproscan/interproscan-5.77-108.0/interproscan.sh",
        "interproscan_threads": 1,
    },
    "context": {
        "window_mode": "genes",
        "upstream": 5,
        "downstream": 5,
        "bp_upstream": 5000,
        "bp_downstream": 5000,
        "include_clusters": True,
    },
    "homology": {
        "search_level": 90,
        "sensitivity": 7.5,
        "evalue": 1e-3,
        "max_seqs": 5000,
        "threads": 1,
        "format_fields": [
            "query",
            "target",
            "pident",
            "alnlen",
            "qcov",
            "tcov",
            "evalue",
            "bits",
            "qlen",
            "tlen",
        ],
    },
    "clusters": {
        "search_level": 90,
        "statistics_neighbor_level": 30,
        "expand_30_contexts": False,
    },
    "colocation": {
        "min_contexts": 3,
        "min_presence_rate": 0.01,
        "min_fold_enrichment": 2.0,
        "max_qvalue": 0.05,
        "max_examples": 5,
        "max_candidates": 100,
        "no_filtering": False,
    },
    "background": {
        "output_dir": "runs/background",
    },
    "sequence": {
        "max_bases": 20000,
    },
    "agent": {
        "query_catalog": None,
        "max_candidates": 50,
        "max_examples": 5,
        "include_sequences": False,
        "flank_bp": 0,
        "notebook": {},
        "program_planner": {
            "max_rounds": 2,
            "prompt_dir": "prompts/agent/reasoning",
            "schema_retries": 2,
        },
        "cohort": {
            "enabled": True,
        },
        "tools": {
            "manifest": "configs/tool_manifest.yaml",
            "max_expensive_tools_per_candidate": None,
            "interproscan": {
                "policy": "on_demand",
            },
            "mmseqs": {
                "max_hits": 25,
            },
        },
        "dynamic_tools": {
            "enabled": False,
            "timeout_seconds": 60,
            "allowed_imports": [
                "Bio",
                "collections",
                "csv",
                "itertools",
                "json",
                "math",
                "re",
                "statistics",
            ],
        },
        "literature": {
            "sources": ["europe_pmc", "pubmed"],
            "max_results_per_source": 5,
        },
        "llm": {
            "mode": "mock",
            "provider": "openai",
            "model_name": None,
            "base_url": None,
            "api_key_env": "OPENAI_API_KEY",
            "temperature": 0.2,
            "max_tokens": 2000,
            "replay_path": None,
        },
        "reporting": {
            "ledger_dir": "ledgers",
        },
    },
    "runtime": {
        "sandbox_dir": "sandbox",
        "cache_dir": "cache",
        "log_dir": "logs",
        "tool_log_mode": "quiet",
        "runs_dir": "runs",
        "progress": True,
        "heartbeat_seconds": 30,
        "event_log": "agent_events.jsonl",
    },
}

CONFIG_RELATIVE_PATHS: tuple[tuple[str, ...], ...] = (
    ("data", "proteins_db"),
    ("data", "clusters_db"),
    ("data", "genome_manifest"),
    ("data", "protein_manifest"),
    ("data", "mmseqs_db_root"),
    ("tools", "mmseqs"),
    ("tools", "interproscan"),
    ("background", "output_dir"),
    ("agent", "query_catalog"),
    ("agent", "program_planner", "prompt_dir"),
    ("agent", "tools", "manifest"),
    ("agent", "llm", "replay_path"),
    ("runtime", "sandbox_dir"),
    ("runtime", "cache_dir"),
    ("runtime", "log_dir"),
    ("runtime", "runs_dir"),
)


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_yaml_config(config_path: Path | str | None) -> dict[str, Any]:
    if config_path is None:
        return {}

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return payload


def load_config(
    config_path: Path | str | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    yaml_config = load_yaml_config(config_path)
    _raise_if_legacy_agent_keys(yaml_config, source=str(config_path) if config_path is not None else "config")
    if config_path is not None:
        yaml_config = resolve_config_paths(yaml_config, base_dir=_config_base_dir(Path(config_path)))
    config = deep_merge(config, yaml_config)
    if cli_overrides:
        _raise_if_legacy_agent_keys(dict(cli_overrides), source="CLI overrides")
        config = deep_merge(config, cli_overrides)
    return config


def resolve_config_paths(config: Mapping[str, Any], *, base_dir: Path | str) -> dict[str, Any]:
    resolved = deepcopy(dict(config))
    base = Path(base_dir)
    for path_keys in CONFIG_RELATIVE_PATHS:
        _resolve_path_value(resolved, path_keys, base)
    return resolved


def _resolve_path_value(config: dict[str, Any], path_keys: tuple[str, ...], base_dir: Path) -> None:
    current: Any = config
    for key in path_keys[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(key)
    if not isinstance(current, dict):
        return
    leaf = path_keys[-1]
    value = current.get(leaf)
    if not isinstance(value, str) or not value:
        return
    path = Path(value).expanduser()
    if path.is_absolute():
        current[leaf] = str(path)
    else:
        current[leaf] = str((base_dir / path).resolve(strict=False))


def _config_base_dir(config_path: Path) -> Path:
    path = config_path.expanduser().resolve(strict=False)
    start = path.parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return start


def _raise_if_legacy_agent_keys(payload: Mapping[str, Any], *, source: str) -> None:
    legacy_hits: list[str] = []
    hints: list[str] = []

    agent = payload.get("agent")
    if not isinstance(agent, Mapping):
        return

    if "workflow" in agent:
        legacy_hits.append("agent.workflow")
        hints.append("remove agent.workflow; falcon now has a single program-driven agent runtime")
    if "team" in agent:
        legacy_hits.append("agent.team")
        hints.append(
            "move agent.team.prompt_dir/schema_retries to agent.program_planner.*, "
            "agent.team.tool_manifest to agent.tools.manifest, and agent.team.ledger_dir to agent.reporting.ledger_dir"
        )
    llm = agent.get("llm")
    if isinstance(llm, Mapping):
        if "prompt_pack" in llm:
            legacy_hits.append("agent.llm.prompt_pack")
            hints.append("remove agent.llm.prompt_pack; prompts now come from agent.program_planner.prompt_dir")
        if "max_iterations" in llm:
            legacy_hits.append("agent.llm.max_iterations")
            hints.append("move agent.llm.max_iterations to agent.program_planner.max_rounds")
        if str(llm.get("mode") or "") == "deterministic":
            legacy_hits.append("agent.llm.mode=deterministic")
            hints.append("set agent.llm.mode to mock, live, or replay; deterministic agent mode was removed")

    if legacy_hits:
        detail = ", ".join(legacy_hits)
        migration = "; ".join(hints)
        raise ValueError(f"{source} uses removed agent configuration keys: {detail}. Migration: {migration}")
