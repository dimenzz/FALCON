from __future__ import annotations

from pathlib import Path
from typing import Any


def is_executable(path: Path | str) -> bool:
    tool_path = Path(path)
    return tool_path.exists() and tool_path.is_file() and tool_path.stat().st_mode & 0o111 != 0


def build_interproscan_command(
    *,
    interproscan_path: Path | str,
    input_fasta: Path | str,
    output_dir: Path | str,
    threads: int,
) -> list[str]:
    return [
        str(interproscan_path),
        "--input",
        str(input_fasta),
        "--output-dir",
        str(output_dir),
        "--formats",
        "tsv",
        "--cpu",
        str(threads),
    ]


def parse_interproscan_tsv(payload: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 13:
            continue
        records.append(
            {
                "analysis": parts[3],
                "signature_accession": parts[4],
                "signature_description": parts[5],
                "start": int(parts[6]),
                "end": int(parts[7]),
                "interpro_accession": None if parts[11] == "-" else parts[11],
                "interpro_description": None if parts[12] == "-" else parts[12],
            }
        )
    return records
