from pathlib import Path
import json
import sys

import pytest

from falcon.agent.team.events import JsonlEventLogger
from falcon.tools.runner import ExternalCommandError, run_external_command


def test_run_external_command_captures_stdout_and_stderr_to_logs(tmp_path: Path) -> None:
    tool = tmp_path / "tool.sh"
    tool.write_text(
        "#!/bin/sh\n"
        "printf 'stdout line\\n'\n"
        "printf 'stderr line\\n' >&2\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)

    trace = run_external_command(
        command=[str(tool)],
        log_dir=tmp_path / "logs",
        label="fake-tool",
    )

    assert trace["return_code"] == 0
    assert Path(trace["stdout_log"]).read_text(encoding="utf-8") == "stdout line\n"
    assert Path(trace["stderr_log"]).read_text(encoding="utf-8") == "stderr line\n"


def test_run_external_command_raises_with_log_paths_on_failure(tmp_path: Path) -> None:
    tool = tmp_path / "tool.sh"
    tool.write_text(
        "#!/bin/sh\n"
        "printf 'failure details\\n' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    tool.chmod(0o755)

    with pytest.raises(ExternalCommandError) as exc_info:
        run_external_command(
            command=[str(tool)],
            log_dir=tmp_path / "logs",
            label="fake-tool",
        )

    assert exc_info.value.return_code == 7
    assert "fake-tool failed with exit code 7" in str(exc_info.value)
    assert Path(exc_info.value.trace["stderr_log"]).read_text(encoding="utf-8") == "failure details\n"


def test_run_external_command_emits_start_heartbeat_and_finish_events(tmp_path: Path) -> None:
    event_log = tmp_path / "agent_events.jsonl"
    logger = JsonlEventLogger(event_log, emit_to_stderr=False)

    trace = run_external_command(
        command=[sys.executable, "-c", "import time; print('ok'); time.sleep(0.2)"],
        log_dir=tmp_path / "logs",
        label="slow-tool",
        event_logger=logger,
        heartbeat_seconds=0.05,
        event_context={"candidate_slug": "candidate-a", "tool": "run_candidate_mmseqs"},
    )

    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    event_types = [event["event"] for event in events]
    assert event_types[0] == "external_command_started"
    assert "external_command_heartbeat" in event_types
    assert event_types[-1] == "external_command_finished"
    assert events[0]["candidate_slug"] == "candidate-a"
    assert events[-1]["return_code"] == 0
    assert events[-1]["stdout_log"] == trace["stdout_log"]
