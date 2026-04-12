from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from falcon.data.manifests import load_manifest
from falcon.data.proteins import ProteinRepository


class SequenceNotFoundError(KeyError):
    def __init__(self, sequence_id: str, fasta_path: Path | str) -> None:
        super().__init__(sequence_id)
        self.sequence_id = sequence_id
        self.fasta_path = str(fasta_path)


class ManifestEntryNotFoundError(KeyError):
    def __init__(self, manifest_key: str, manifest_path: Path | str) -> None:
        super().__init__(manifest_key)
        self.manifest_key = manifest_key
        self.manifest_path = str(manifest_path)


class SequenceTooLargeError(ValueError):
    def __init__(self, protein_id: str, requested_bases: int, max_bases: int) -> None:
        self.protein_id = protein_id
        self.requested_bases = requested_bases
        self.max_bases = max_bases
        super().__init__(
            f"DNA sequence for {protein_id!r} spans {requested_bases} bp; "
            f"maximum allowed is {max_bases} bp"
        )


class SequenceRepository:
    def __init__(
        self,
        *,
        proteins_db: Path | str,
        protein_manifest: Path | str,
        genome_manifest: Path | str,
    ) -> None:
        self._proteins = ProteinRepository(proteins_db)
        self._protein_manifest_path = Path(protein_manifest)
        self._genome_manifest_path = Path(genome_manifest)
        self._protein_manifest = load_manifest(protein_manifest)
        self._genome_manifest = load_manifest(genome_manifest)

    def close(self) -> None:
        self._proteins.close()

    def __enter__(self) -> "SequenceRepository":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def get_protein_sequence(self, protein_id: str) -> dict[str, Any]:
        protein = self._proteins.get(protein_id)
        fasta_path = self._manifest_path(
            self._protein_manifest,
            self._protein_manifest_path,
            str(protein["mag_id"]),
        )
        sequence = _read_fasta_record(fasta_path, protein_id)
        return {
            "protein_id": protein_id,
            "mag_id": protein["mag_id"],
            "fasta_path": str(fasta_path),
            "sequence": sequence,
            "length": len(sequence),
        }

    def get_dna_for_protein(
        self,
        protein_id: str,
        *,
        flank_bp: int = 0,
        max_bases: int = 20000,
        orientation: str = "protein",
    ) -> dict[str, Any]:
        protein = self._proteins.get(protein_id)
        fasta_path = self._manifest_path(
            self._genome_manifest,
            self._genome_manifest_path,
            str(protein["mag_id"]),
        )
        contig_sequence = _read_fasta_record(fasta_path, str(protein["contig_id"]))
        start = max(1, int(protein["start"]) - int(flank_bp))
        end = min(len(contig_sequence), int(protein["end"]) + int(flank_bp))
        span = end - start + 1
        if span > int(max_bases):
            raise SequenceTooLargeError(protein_id, span, int(max_bases))

        sequence = contig_sequence[start - 1 : end]
        if orientation == "protein" and str(protein["strand"]) == "-":
            sequence = _reverse_complement(sequence)
        elif orientation not in {"protein", "contig"}:
            raise ValueError("orientation must be 'protein' or 'contig'")

        return {
            "protein_id": protein_id,
            "mag_id": protein["mag_id"],
            "contig_id": protein["contig_id"],
            "fasta_path": str(fasta_path),
            "start": start,
            "end": end,
            "strand": protein["strand"],
            "orientation": orientation,
            "flank_bp": int(flank_bp),
            "sequence": sequence,
            "length": len(sequence),
        }

    @staticmethod
    def _manifest_path(
        manifest: dict[str, str],
        manifest_path: Path,
        manifest_key: str,
    ) -> Path:
        try:
            return Path(manifest[manifest_key])
        except KeyError as exc:
            raise ManifestEntryNotFoundError(manifest_key, manifest_path) from exc


def _read_fasta_record(fasta_path: Path | str, sequence_id: str) -> str:
    for record_id, sequence in _iter_fasta(fasta_path):
        if record_id == sequence_id:
            return sequence
    raise SequenceNotFoundError(sequence_id, fasta_path)


def _iter_fasta(fasta_path: Path | str) -> Iterator[tuple[str, str]]:
    current_id: str | None = None
    chunks: list[str] = []
    with Path(fasta_path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    yield current_id, "".join(chunks)
                current_id = line[1:].split()[0]
                chunks = []
            else:
                chunks.append(line)
    if current_id is not None:
        yield current_id, "".join(chunks)


def _reverse_complement(sequence: str) -> str:
    table = str.maketrans("ACGTRYKMSWBDHVNacgtrykmswbdhvn", "TGCAYRMKSWVHDBNtgcayrmkswvhdbn")
    return sequence.translate(table)[::-1]
