from __future__ import annotations

from pathlib import Path
import json


def load_query_catalog(path: Path | str) -> dict[str, dict[str, str | None]]:
    catalog: dict[str, dict[str, str | None]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("query catalog rows must be JSON objects")
            query_id = str(payload.get("query_id") or "").strip()
            if not query_id:
                raise ValueError("query catalog rows must define query_id")
            catalog[query_id] = {
                "query_id": query_id,
                "header_description": _string_or_none(payload.get("header_description")),
                "function_description": _string_or_none(payload.get("function_description")),
            }
    return catalog


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
