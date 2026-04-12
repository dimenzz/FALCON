from pathlib import Path

import pytest

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
