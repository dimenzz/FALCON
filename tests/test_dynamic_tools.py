from pathlib import Path

from falcon.tools.dynamic import DynamicPythonToolRunner, validate_dynamic_python_script


def test_dynamic_python_validator_rejects_nested_subprocess() -> None:
    result = validate_dynamic_python_script(
        """
import subprocess

def run(input_payload):
    subprocess.run(["echo", "bad"])
    return {"status": "ok"}
"""
    )

    assert result.approved is False
    assert "import not allowed: subprocess" in result.errors
    assert "call not allowed: subprocess.run" in result.errors


def test_dynamic_python_tool_runs_reviewed_script_and_records_artifacts(tmp_path: Path) -> None:
    runner = DynamicPythonToolRunner(output_dir=tmp_path / "dynamic", log_dir=tmp_path / "logs")

    result = runner.run(
        script_source="""
from Bio.Seq import Seq

def run(input_payload):
    seq = Seq(input_payload["sequence"])
    return {
        "status": "ok",
        "answer": str(seq.reverse_complement()),
        "observations": [{"length": len(seq)}],
        "evidence_refs": [],
        "limitations": []
    }
""",
        input_payload={"sequence": "ATGC"},
        label="reverse-complement",
    )

    assert result["status"] == "ok"
    assert result["result"]["answer"] == "GCAT"
    assert Path(result["script_path"]).exists()
    assert Path(result["input_path"]).exists()
    assert Path(result["output_path"]).exists()
    assert result["script_sha256"]
