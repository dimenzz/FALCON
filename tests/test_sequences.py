from pathlib import Path
import sqlite3

import pytest

from falcon.data.sequences import SequenceRepository, SequenceTooLargeError


def create_sequence_proteins_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE proteins (
                protein_id TEXT PRIMARY KEY,
                contig_id TEXT NOT NULL,
                mag_id TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                strand TEXT NOT NULL,
                length INTEGER NOT NULL,
                product TEXT,
                gene_name TEXT,
                locus_tag TEXT,
                pfam TEXT,
                interpro TEXT,
                kegg TEXT,
                cog_category TEXT,
                cog_id TEXT,
                ec_number TEXT,
                eggnog TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO proteins (
                protein_id, contig_id, mag_id, start, end, strand, length,
                product, gene_name, locus_tag, pfam, interpro, kegg,
                cog_category, cog_id, ec_number, eggnog
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("p_plus", "contigA", "magA", 2, 5, "+", 1, "plus", None, None, None, None, None, None, None, None, None),
                ("p_minus", "contigA", "magA", 7, 10, "-", 1, "minus", None, None, None, None, None, None, None, None, None),
            ],
        )


def create_sequence_files(tmp_path: Path) -> tuple[Path, Path]:
    protein_fasta = tmp_path / "magA.faa"
    genome_fasta = tmp_path / "magA.fna"
    protein_manifest = tmp_path / "protein_manifest.csv"
    genome_manifest = tmp_path / "genome_manifest.csv"
    protein_fasta.write_text(
        ">p_plus protein\nMKT\n"
        ">p_minus protein\nQQQ\n",
        encoding="utf-8",
    )
    genome_fasta.write_text(
        ">contigA genome\n"
        "AACCGTTACTCC\n",
        encoding="utf-8",
    )
    protein_manifest.write_text(f"magA,{protein_fasta}\n", encoding="utf-8")
    genome_manifest.write_text(f"magA,{genome_fasta}\n", encoding="utf-8")
    return protein_manifest, genome_manifest


def test_sequence_repository_reads_protein_sequence_by_protein_id(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    create_sequence_proteins_db(proteins_db)
    protein_manifest, genome_manifest = create_sequence_files(tmp_path)

    with SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        record = sequences.get_protein_sequence("p_plus")

    assert record["protein_id"] == "p_plus"
    assert record["sequence"] == "MKT"
    assert record["fasta_path"].endswith("magA.faa")


def test_sequence_repository_reads_dna_for_negative_strand_in_protein_orientation(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    create_sequence_proteins_db(proteins_db)
    protein_manifest, genome_manifest = create_sequence_files(tmp_path)

    with SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        record = sequences.get_dna_for_protein("p_minus", flank_bp=1, max_bases=20)

    assert record["protein_id"] == "p_minus"
    assert record["contig_id"] == "contigA"
    assert record["start"] == 6
    assert record["end"] == 11
    assert record["strand"] == "-"
    assert record["orientation"] == "protein"
    assert record["sequence"] == "GAGTAA"


def test_sequence_repository_refuses_dna_span_above_limit(tmp_path: Path) -> None:
    proteins_db = tmp_path / "proteins.db"
    create_sequence_proteins_db(proteins_db)
    protein_manifest, genome_manifest = create_sequence_files(tmp_path)

    with SequenceRepository(
        proteins_db=proteins_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
    ) as sequences:
        with pytest.raises(SequenceTooLargeError):
            sequences.get_dna_for_protein("p_minus", flank_bp=3, max_bases=4)
