from __future__ import annotations

from pathlib import Path

from falcon.data.sqlite import connect_readonly


class ClusterRepository:
    def __init__(self, db_path: Path | str) -> None:
        self._connection = connect_readonly(db_path)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ClusterRepository":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def representatives_for_members(self, member_ids: list[str]) -> dict[str, dict[str, str]]:
        if not member_ids:
            return {}

        placeholders = ",".join("?" for _ in member_ids)
        rows = self._connection.execute(
            f"""
            SELECT member_id, cluster_level, representative_id
            FROM clusters
            WHERE member_id IN ({placeholders})
            ORDER BY member_id, cluster_level
            """,
            member_ids,
        ).fetchall()

        result: dict[str, dict[str, str]] = {member_id: {} for member_id in member_ids}
        for row in rows:
            result[row["member_id"]][str(row["cluster_level"])] = row["representative_id"]
        return result

    def representative_for_member(self, member_id: str, cluster_level: int | str) -> str | None:
        row = self._connection.execute(
            """
            SELECT representative_id
            FROM clusters
            WHERE member_id = ? AND cluster_level = ?
            """,
            (member_id, str(cluster_level)),
        ).fetchone()
        return row["representative_id"] if row is not None else None

    def members_for_representative(self, representative_id: str, cluster_level: int | str) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT member_id
            FROM clusters
            WHERE representative_id = ? AND cluster_level = ?
            ORDER BY member_id
            """,
            (representative_id, str(cluster_level)),
        ).fetchall()
        return [row["member_id"] for row in rows]
