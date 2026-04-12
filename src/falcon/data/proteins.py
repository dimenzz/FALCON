from __future__ import annotations

from pathlib import Path
from typing import Any

from falcon.data.sqlite import connect_readonly


class ProteinNotFoundError(KeyError):
    def __init__(self, protein_id: str) -> None:
        super().__init__(protein_id)
        self.protein_id = protein_id


class ProteinRepository:
    def __init__(self, db_path: Path | str) -> None:
        self._connection = connect_readonly(db_path)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ProteinRepository":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def get(self, protein_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT * FROM proteins WHERE protein_id = ?",
            (protein_id,),
        ).fetchone()
        if row is None:
            raise ProteinNotFoundError(protein_id)
        return dict(row)

    def contig_proteins(self, contig_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM proteins
            WHERE contig_id = ?
            ORDER BY start, end, protein_id
            """,
            (contig_id,),
        ).fetchall()
        return [dict(row) for row in rows]
