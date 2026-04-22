from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SeedSummary:
    query_id: str
    query_prior: dict[str, Any]
    target_consensus_annotation: dict[str, Any]
    note: str

    @classmethod
    def from_query_and_examples(
        cls,
        *,
        query_record: dict[str, Any],
        examples: list[dict[str, Any]],
    ) -> "SeedSummary":
        query_id = str(query_record.get("query_id") or "").strip()
        if not query_id:
            raise ValueError("query_record must define query_id")
        return cls(
            query_id=query_id,
            query_prior={
                "query_id": query_id,
                "header_description": _string_or_none(query_record.get("header_description")),
                "function_description": _string_or_none(query_record.get("function_description")),
                "confidence": "soft_prior",
            },
            target_consensus_annotation=_target_consensus(examples),
            note=(
                "Seed query descriptions are soft priors from the user-provided FASTA header or metadata TSV. "
                "They guide planning and literature framing, but they are not direct evidence for candidate claims."
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _target_consensus(examples: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("product", "gene_name", "pfam", "interpro", "kegg", "cog_id", "cog_category")
    counters = {field: Counter() for field in fields}
    protein_ids: list[str] = []
    for example in examples:
        target = ((example.get("context") or {}).get("target") or {})
        protein_id = _string_or_none(target.get("protein_id"))
        if protein_id:
            protein_ids.append(protein_id)
        for field in fields:
            value = _string_or_none(target.get(field))
            if value:
                counters[field][value] += 1
    summary = {field: _most_common(counter) for field, counter in counters.items()}
    summary["protein_ids"] = protein_ids
    return summary


def _most_common(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
