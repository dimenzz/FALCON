from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sys


class JsonlEventLogger:
    def __init__(self, path: Path | str, *, emit_to_stderr: bool = True) -> None:
        self.path = Path(path)
        self.emit_to_stderr = emit_to_stderr
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **payload: Any) -> None:
        record = {
            "timestamp": _utc_timestamp(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        if self.emit_to_stderr:
            print(_format_progress(record), file=sys.stderr, flush=True)


class NoopEventLogger:
    def emit(self, event: str, **payload: Any) -> None:
        return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_progress(record: dict[str, Any]) -> str:
    parts = [f"[falcon] {record['event']}"]
    for key in ("candidate_slug", "role", "tool", "label", "elapsed_seconds", "return_code"):
        value = record.get(key)
        if value is not None:
            parts.append(f"{key}={value}")
    if record.get("stdout_log"):
        parts.append(f"stdout_log={record['stdout_log']}")
    if record.get("stderr_log"):
        parts.append(f"stderr_log={record['stderr_log']}")
    return " ".join(parts)
