from __future__ import annotations

from pathlib import Path
import csv


def load_manifest(path: Path | str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) != 2:
                raise ValueError(f"Manifest row {row_number} must have exactly two columns")
            genome_id, fasta_path = row
            manifest[genome_id] = fasta_path
    return manifest


def inspect_manifest(path: Path | str) -> dict[str, object]:
    manifest_path = Path(path)
    result: dict[str, object] = {
        "path": str(manifest_path),
        "exists": manifest_path.exists(),
        "ok": False,
    }
    if not manifest_path.exists():
        result["error"] = "path does not exist"
        return result

    try:
        with manifest_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            first_row = next((row for row in reader if row), None)
    except OSError as exc:
        result["error"] = str(exc)
        return result

    result["first_row"] = first_row
    result["ok"] = first_row is not None and len(first_row) == 2
    if not result["ok"]:
        result["error"] = "manifest must contain two-column rows"
    return result
