from pathlib import Path

from falcon.homology.seeds import load_seed_records


def test_load_seed_records_parses_multifasta_headers(tmp_path: Path) -> None:
    fasta_path = tmp_path / "seeds.faa"
    fasta_path.write_text(
        ">q1 candidate nuclease\n"
        "MKT\n"
        "AA\n"
        ">q2\n"
        "GGG\n",
        encoding="utf-8",
    )

    seeds, warnings = load_seed_records(fasta_path)

    assert [seed.query_id for seed in seeds] == ["q1", "q2"]
    assert seeds[0].sequence == "MKTAA"
    assert seeds[0].header_description == "candidate nuclease"
    assert seeds[0].function_description == "candidate nuclease"
    assert seeds[1].function_description is None
    assert warnings == ["Seed q2 has no function description"]


def test_seed_metadata_tsv_overrides_header_description(tmp_path: Path) -> None:
    fasta_path = tmp_path / "seeds.faa"
    metadata_path = tmp_path / "metadata.tsv"
    fasta_path.write_text(">q1 vague header\nMKT\n", encoding="utf-8")
    metadata_path.write_text(
        "query_id\tfunction_description\n"
        "q1\tATP-dependent helicase seed\n",
        encoding="utf-8",
    )

    seeds, warnings = load_seed_records(fasta_path, metadata_path)

    assert seeds[0].header_description == "vague header"
    assert seeds[0].function_description == "ATP-dependent helicase seed"
    assert warnings == []
