from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import os
import re
import subprocess
import time


class ExternalCommandError(RuntimeError):
    def __init__(self, label: str, return_code: int, trace: dict[str, Any]) -> None:
        self.label = label
        self.return_code = return_code
        self.trace = trace
        super().__init__(
            f"{label} failed with exit code {return_code}; "
            f"stdout log: {trace['stdout_log']}; stderr log: {trace['stderr_log']}"
        )


@dataclass(frozen=True)
class ExternalCommandTrace:
    label: str
    command: list[str]
    return_code: int
    stdout_log: str
    stderr_log: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "command": self.command,
            "return_code": self.return_code,
            "stdout_log": self.stdout_log,
            "stderr_log": self.stderr_log,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def run_external_command(
    *,
    command: Sequence[str],
    log_dir: Path | str,
    label: str,
    env: Mapping[str, str] | None = None,
    event_logger: Any | None = None,
    heartbeat_seconds: float | None = None,
    event_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    logs = Path(log_dir)
    logs.mkdir(parents=True, exist_ok=True)
    started_at = _utc_timestamp()
    stem = f"{_safe_label(label)}-{started_at.replace(':', '').replace('-', '')}"
    stdout_log = logs / f"{stem}.stdout.log"
    stderr_log = logs / f"{stem}.stderr.log"
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    context = dict(event_context or {})
    if event_logger is not None:
        event_logger.emit(
            "external_command_started",
            **context,
            label=label,
            command=list(command),
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
        )

    with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            list(command),
            env=run_env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        started_monotonic = time.monotonic()
        if event_logger is None or heartbeat_seconds is None or heartbeat_seconds <= 0:
            return_code = process.wait()
        else:
            next_heartbeat = started_monotonic + float(heartbeat_seconds)
            while True:
                return_code = process.poll()
                if return_code is not None:
                    break
                now = time.monotonic()
                if now >= next_heartbeat:
                    event_logger.emit(
                        "external_command_heartbeat",
                        **context,
                        label=label,
                        elapsed_seconds=round(now - started_monotonic, 3),
                        stdout_log=str(stdout_log),
                        stderr_log=str(stderr_log),
                    )
                    next_heartbeat = now + float(heartbeat_seconds)
                time.sleep(min(0.1, max(float(heartbeat_seconds) / 2, 0.01)))

    trace = ExternalCommandTrace(
        label=label,
        command=list(command),
        return_code=return_code,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        started_at=started_at,
        finished_at=_utc_timestamp(),
    ).to_dict()
    if event_logger is not None:
        event_logger.emit(
            "external_command_finished" if return_code == 0 else "external_command_failed",
            **context,
            label=label,
            return_code=return_code,
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
        )
    if return_code != 0:
        raise ExternalCommandError(label, return_code, trace)
    return trace


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_label(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "tool"
