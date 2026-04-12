from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
import json

from falcon.tools.runner import run_external_command


DEFAULT_FORMAT_FIELDS = [
    "query",
    "target",
    "pident",
    "alnlen",
    "qcov",
    "tcov",
    "evalue",
    "bits",
    "qlen",
    "tlen",
]


@dataclass(frozen=True)
class HomologyHit:
    query_id: str
    target_id: str
    pident: float
    alnlen: int
    qcov: float
    tcov: float
    evalue: float
    bits: float
    qlen: int
    tlen: int
    search_level: int
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HomologyHit":
        return cls(
            query_id=str(payload["query_id"]),
            target_id=str(payload["target_id"]),
            pident=float(payload["pident"]),
            alnlen=int(payload["alnlen"]),
            qcov=float(payload["qcov"]),
            tcov=float(payload["tcov"]),
            evalue=float(payload["evalue"]),
            bits=float(payload["bits"]),
            qlen=int(payload["qlen"]),
            tlen=int(payload["tlen"]),
            search_level=int(payload["search_level"]),
            rank=int(payload["rank"]),
        )


def target_db_for_level(mmseqs_db_root: Path | str, search_level: int) -> Path:
    level = int(search_level)
    return Path(mmseqs_db_root) / f"cluster_{level}" / f"all_proteins_{level}"


def run_mmseqs_search(
    *,
    mmseqs_path: Path | str,
    query_fasta: Path | str,
    target_db: Path | str,
    output_tsv: Path | str,
    tmp_dir: Path | str,
    sensitivity: float,
    evalue: float,
    max_seqs: int,
    threads: int,
    format_fields: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    log_dir: Path | str = "logs",
) -> dict[str, Any]:
    output_path = Path(output_tsv)
    tmp_path = Path(tmp_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    fields = format_fields or DEFAULT_FORMAT_FIELDS
    command = [
        str(mmseqs_path),
        "easy-search",
        str(query_fasta),
        str(target_db),
        str(output_path),
        str(tmp_path),
        "-s",
        str(sensitivity),
        "-e",
        str(evalue),
        "--max-seqs",
        str(max_seqs),
        "--threads",
        str(threads),
        "--format-output",
        ",".join(fields),
    ]
    return run_external_command(
        command=command,
        log_dir=log_dir,
        label="mmseqs-easy-search",
        env=env,
    )


def parse_hits_tsv(path: Path | str, search_level: int) -> list[HomologyHit]:
    hits: list[HomologyHit] = []
    ranks_by_query: dict[str, int] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            columns = line.split("\t")
            if len(columns) != len(DEFAULT_FORMAT_FIELDS):
                raise ValueError(
                    f"MMseqs row {line_number} has {len(columns)} columns; expected {len(DEFAULT_FORMAT_FIELDS)}"
                )
            query_id = columns[0]
            ranks_by_query[query_id] = ranks_by_query.get(query_id, 0) + 1
            hits.append(
                HomologyHit(
                    query_id=query_id,
                    target_id=columns[1],
                    pident=float(columns[2]),
                    alnlen=int(columns[3]),
                    qcov=float(columns[4]),
                    tcov=float(columns[5]),
                    evalue=float(columns[6]),
                    bits=float(columns[7]),
                    qlen=int(columns[8]),
                    tlen=int(columns[9]),
                    search_level=int(search_level),
                    rank=ranks_by_query[query_id],
                )
            )
    return hits


def write_hits_jsonl(hits: list[HomologyHit], path: Path | str) -> None:
    write_jsonl([hit.to_dict() for hit in hits], path)


def read_hits_jsonl(path: Path | str) -> list[HomologyHit]:
    hits: list[HomologyHit] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                hits.append(HomologyHit.from_dict(json.loads(line)))
    return hits


def write_jsonl(items: list[Mapping[str, Any]], path: Path | str) -> None:
    jsonl_path = Path(path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(dict(item), sort_keys=True) + "\n")
