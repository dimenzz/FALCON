from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv


@dataclass(frozen=True)
class SeedRecord:
    query_id: str
    sequence: str
    header_description: str | None
    function_description: str | None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def load_seed_records(
    fasta_path: Path | str,
    metadata_path: Path | str | None = None,
) -> tuple[list[SeedRecord], list[str]]:
    metadata = load_seed_metadata(metadata_path) if metadata_path is not None else {}
    records: list[SeedRecord] = []
    warnings: list[str] = []

    for query_id, header_description, sequence in parse_fasta(fasta_path):
        function_description = metadata.get(query_id) or header_description
        if not function_description:
            warnings.append(f"Seed {query_id} has no function description")
        records.append(
            SeedRecord(
                query_id=query_id,
                sequence=sequence,
                header_description=header_description,
                function_description=function_description,
            )
        )

    return records, warnings


def parse_fasta(path: Path | str) -> list[tuple[str, str | None, str]]:
    records: list[tuple[str, str | None, str]] = []
    current_id: str | None = None
    current_description: str | None = None
    sequence_parts: list[str] = []

    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    records.append((current_id, current_description, "".join(sequence_parts)))
                header = line[1:].strip()
                if not header:
                    raise ValueError(f"FASTA header on line {line_number} is empty")
                parts = header.split(maxsplit=1)
                current_id = parts[0]
                current_description = parts[1] if len(parts) == 2 else None
                sequence_parts = []
            else:
                if current_id is None:
                    raise ValueError(f"FASTA sequence appears before a header on line {line_number}")
                sequence_parts.append(line)

    if current_id is not None:
        records.append((current_id, current_description, "".join(sequence_parts)))

    if not records:
        raise ValueError(f"No FASTA records found in {path}")
    return records


def load_seed_metadata(path: Path | str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if row_number == 1 and _is_header(row):
                continue
            if len(row) != 2:
                raise ValueError(f"Seed metadata row {row_number} must have exactly two columns")
            query_id, function_description = row
            metadata[query_id] = function_description
    return metadata


def write_seeds_jsonl(seeds: list[SeedRecord], path: Path | str) -> None:
    from falcon.homology.search import write_jsonl

    write_jsonl([seed.to_dict() for seed in seeds], path)


def _is_header(row: list[str]) -> bool:
    normalized = [value.strip().lower() for value in row]
    return normalized == ["query_id", "function_description"]
