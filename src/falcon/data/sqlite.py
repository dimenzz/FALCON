from __future__ import annotations

from pathlib import Path
import sqlite3


def connect_readonly(path: Path | str) -> sqlite3.Connection:
    db_path = Path(path).expanduser().resolve()
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def list_tables(path: Path | str) -> list[str]:
    with connect_readonly(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def table_columns(path: Path | str, table_name: str) -> list[str]:
    with connect_readonly(path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def inspect_sqlite(path: Path | str, expected_tables: list[str] | None = None) -> dict[str, object]:
    db_path = Path(path)
    result: dict[str, object] = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "ok": False,
        "tables": [],
    }
    if not db_path.exists():
        result["error"] = "path does not exist"
        return result

    try:
        tables = list_tables(db_path)
        result["tables"] = tables
        result["columns"] = {table: table_columns(db_path, table) for table in tables}
    except sqlite3.Error as exc:
        result["error"] = str(exc)
        return result

    if expected_tables:
        missing = sorted(set(expected_tables) - set(tables))
        result["missing_tables"] = missing
        result["ok"] = not missing
    else:
        result["ok"] = True
    return result
