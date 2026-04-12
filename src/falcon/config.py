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
        "min_presence_rate": 0.1,
        "min_fold_enrichment": 2.0,
        "max_qvalue": 0.05,
        "max_examples": 5,
        "no_filtering": False,
    },
    "background": {
        "output_dir": "runs/background",
    },
    "sequence": {
        "max_bases": 20000,
    },
    "agent": {
        "max_candidates": 50,
        "max_examples": 5,
        "include_sequences": False,
        "flank_bp": 0,
    },
    "runtime": {
        "sandbox_dir": "sandbox",
        "cache_dir": "cache",
        "log_dir": "logs",
        "tool_log_mode": "quiet",
        "runs_dir": "runs",
    },
}


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
    config = deep_merge(config, load_yaml_config(config_path))
    if cli_overrides:
        config = deep_merge(config, cli_overrides)
    return config
