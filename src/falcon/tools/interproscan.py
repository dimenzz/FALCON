from __future__ import annotations

from pathlib import Path


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
        "--cpu",
        str(threads),
    ]
