from __future__ import annotations

from pathlib import Path


def is_executable(path: Path | str) -> bool:
    tool_path = Path(path)
    return tool_path.exists() and tool_path.is_file() and tool_path.stat().st_mode & 0o111 != 0
