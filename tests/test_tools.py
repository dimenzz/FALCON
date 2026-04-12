from pathlib import Path

from falcon.tools.interproscan import build_interproscan_command


def test_interproscan_command_includes_cpu_when_threads_configured(tmp_path: Path) -> None:
    command = build_interproscan_command(
        interproscan_path=tmp_path / "interproscan.sh",
        input_fasta=tmp_path / "query.faa",
        output_dir=tmp_path / "out",
        threads=12,
    )

    assert command == [
        str(tmp_path / "interproscan.sh"),
        "--input",
        str(tmp_path / "query.faa"),
        "--output-dir",
        str(tmp_path / "out"),
        "--cpu",
        "12",
    ]
