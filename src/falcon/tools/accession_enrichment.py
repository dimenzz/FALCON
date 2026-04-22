from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import json
import re
from urllib.parse import quote
from urllib.request import urlopen


FetchFn = Callable[[str], dict[str, Any]]


@dataclass
class AccessionEnricher:
    fetchers: dict[str, FetchFn] | None = None
    timeout_seconds: int = 15

    def __post_init__(self) -> None:
        if self.fetchers is None:
            self.fetchers = {
                "COG": self._fetch_cog,
                "KEGG": self._fetch_kegg,
                "Pfam": self._fetch_pfam,
                "InterPro": self._fetch_interpro,
            }

    def enrich_candidate(self, representative_neighbor: dict[str, Any], *, cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
        accessions = _collect_accessions(representative_neighbor)
        return self.enrich_accessions(accessions, cache_dir=cache_dir)

    def enrich_accessions(
        self,
        accessions: dict[str, list[str]],
        *,
        cache_dir: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for source, accession_list in accessions.items():
            fetch = (self.fetchers or {}).get(source)
            if fetch is None:
                continue
            for accession in accession_list:
                cached = _read_cache(cache_dir, source, accession) if cache_dir is not None else None
                if cached is None:
                    try:
                        cached = fetch(accession)
                    except Exception as exc:
                        cached = {
                            "source": source,
                            "accession": accession,
                            "family_terms": [],
                            "raw_label": "",
                            "status": "unresolved",
                            "reason": str(exc),
                        }
                    if cache_dir is not None:
                        _write_cache(cache_dir, source, accession, cached)
                records.append(_normalize_record(source=source, accession=accession, payload=cached))
        return records

    def _fetch_cog(self, accession: str) -> dict[str, Any]:
        url = (
            "https://www.ncbi.nlm.nih.gov/research/cog/api/cogdef/"
            f"?cog={quote(accession)}&format=json"
        )
        payload = _fetch_json(url, timeout_seconds=self.timeout_seconds)
        label = _extract_first_text(payload, keys=("name", "description", "label", "title"))
        return {"source": "COG", "accession": accession, "family_terms": _family_terms_from_label(label), "raw_label": label}

    def _fetch_kegg(self, accession: str) -> dict[str, Any]:
        token = accession if accession.startswith("K") else accession.split(":")[-1]
        url = f"https://rest.kegg.jp/get/ko:{quote(token)}"
        text = _fetch_text(url, timeout_seconds=self.timeout_seconds)
        label = _parse_kegg_label(text)
        return {"source": "KEGG", "accession": token, "family_terms": _family_terms_from_label(label), "raw_label": label}

    def _fetch_pfam(self, accession: str) -> dict[str, Any]:
        url = f"https://www.ebi.ac.uk/interpro/api/entry/pfam/{quote(accession)}"
        payload = _fetch_json(url, timeout_seconds=self.timeout_seconds)
        label = _extract_interpro_label(payload)
        return {"source": "Pfam", "accession": accession, "family_terms": _family_terms_from_label(label), "raw_label": label}

    def _fetch_interpro(self, accession: str) -> dict[str, Any]:
        url = f"https://www.ebi.ac.uk/interpro/api/entry/interpro/{quote(accession)}"
        payload = _fetch_json(url, timeout_seconds=self.timeout_seconds)
        label = _extract_interpro_label(payload)
        return {"source": "InterPro", "accession": accession, "family_terms": _family_terms_from_label(label), "raw_label": label}


def _collect_accessions(representative_neighbor: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "COG": _split_tokens(representative_neighbor.get("cog_id")),
        "KEGG": [token.split(":")[-1] for token in _split_tokens(representative_neighbor.get("kegg"))],
        "Pfam": _split_tokens(representative_neighbor.get("pfam")),
        "InterPro": _split_tokens(representative_neighbor.get("interpro")),
    }


def _split_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[;,|\s]+", str(value))
    return sorted({item.strip() for item in items if item and item.strip()})


def _read_cache(cache_dir: str | Path | None, source: str, accession: str) -> dict[str, Any] | None:
    if cache_dir is None:
        return None
    path = Path(cache_dir) / "accession" / source.lower() / f"{accession}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(cache_dir: str | Path, source: str, accession: str, payload: dict[str, Any]) -> None:
    path = Path(cache_dir) / "accession" / source.lower() / f"{accession}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_record(*, source: str, accession: str, payload: dict[str, Any]) -> dict[str, Any]:
    label = str(payload.get("raw_label") or "").strip()
    family_terms = payload.get("family_terms") or _family_terms_from_label(label)
    return {
        "source": source,
        "accession": accession,
        "family_terms": [term for term in family_terms if term],
        "raw_label": label,
        "status": payload.get("status", "ok"),
        "reason": payload.get("reason", ""),
    }


def _fetch_json(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, list):
        return payload[0] if payload else {}
    return payload if isinstance(payload, dict) else {}


def _fetch_text(url: str, *, timeout_seconds: int) -> str:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _parse_kegg_label(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("NAME"):
            return line.split("NAME", 1)[1].strip().rstrip(";")
        if line.startswith("DEFINITION"):
            return line.split("DEFINITION", 1)[1].strip()
    return ""


def _extract_interpro_label(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("name", "description", "label", "short_name"):
            value = metadata.get(key)
            if isinstance(value, dict):
                value = value.get("name")
            if value:
                return str(value)
    for key in ("name", "description", "label", "title"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _extract_first_text(payload: dict[str, Any], *, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    results = payload.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            for key in keys:
                value = item.get(key)
                if value:
                    return str(value)
    return ""


def _family_terms_from_label(label: str) -> list[str]:
    if not label:
        return []
    patterns = [
        r"\b(Cas\d+[A-Za-z0-9-]*)\b",
        r"\b(Csn\d+[A-Za-z0-9-]*)\b",
        r"\b(Acr[A-Za-z0-9-]+)\b",
        r"\b(UPF\d+)\b",
        r"\b(DUF\d+)\b",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, label)
        if matches:
            return sorted(set(matches))
    cleaned = re.sub(r"(?i)\bcrispr-associated protein\b", "", label)
    cleaned = re.sub(r"(?i)\bfamily protein\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bfamily\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bprotein\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;")
    return [cleaned] if cleaned and "hypothetical" not in cleaned.lower() else []
