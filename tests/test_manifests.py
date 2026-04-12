from pathlib import Path

from falcon.data.manifests import load_manifest


def test_load_manifest_reads_two_column_csv(tmp_path: Path) -> None:
    manifest_path = tmp_path / "protein_manifest.csv"
    manifest_path.write_text(
        "MGYG0001,/data/proteins/MGYG0001.faa\n"
        "MGYG0002,/data/proteins/MGYG0002.faa\n",
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert manifest["MGYG0001"] == "/data/proteins/MGYG0001.faa"
    assert manifest["MGYG0002"] == "/data/proteins/MGYG0002.faa"
