from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class ToolManifestError(ValueError):
    pass


CostTier = Literal["cheap", "moderate", "expensive"]


class ToolSpec(BaseModel):
    id: str
    runner: str
    description: str
    evidence_type: str
    cost_tier: CostTier = "cheap"
    estimated_runtime: str = "seconds"
    enabled: bool = True
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    answers: list[str] = Field(default_factory=list)
    cannot_answer: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    evidence_granularity: str = "unspecified"
    examples: list[dict[str, Any]] = Field(default_factory=list)
    supports_dynamic_fallback: bool = False
    when_to_use: list[str] = Field(default_factory=list)
    when_not_to_use: list[str] = Field(default_factory=list)

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "evidence_type": self.evidence_type,
            "cost_tier": self.cost_tier,
            "estimated_runtime": self.estimated_runtime,
            "enabled": self.enabled,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "answers": list(self.answers),
            "cannot_answer": list(self.cannot_answer),
            "required_artifacts": list(self.required_artifacts),
            "output_contract": dict(self.output_contract),
            "evidence_granularity": self.evidence_granularity,
            "examples": [dict(example) for example in self.examples],
            "supports_dynamic_fallback": self.supports_dynamic_fallback,
            "when_to_use": list(self.when_to_use),
            "when_not_to_use": list(self.when_not_to_use),
        }


class ToolManifest(BaseModel):
    tools: list[ToolSpec]

    def to_prompt_payload(self) -> list[dict[str, Any]]:
        return [tool.to_prompt_payload() for tool in self.tools]

    def tool_ids(self) -> set[str]:
        return {tool.id for tool in self.tools}

    def enabled_tool_ids(self) -> set[str]:
        return {tool.id for tool in self.tools if tool.enabled}

    def get(self, tool_id: str) -> ToolSpec | None:
        for tool in self.tools:
            if tool.id == tool_id:
                return tool
        return None


def default_tool_manifest() -> ToolManifest:
    return ToolManifest(
        tools=[
            ToolSpec(
                id="search_literature",
                runner="search_literature",
                description="Search configured literature sources for prior biological knowledge and terminology constraints.",
                evidence_type="literature",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={"query": "string", "max_results": "integer optional"},
                output_schema={"records": "list of normalized literature records"},
                answers=["published background knowledge, terminology, and known biological constraints"],
                cannot_answer=["candidate-specific function", "local genomic context", "sequence motif conservation"],
                output_contract={"records": "normalized literature records with provenance"},
                evidence_granularity="literature",
                when_to_use=["The candidate hypothesis needs literature grounding or terminology constraints."],
                when_not_to_use=["The same query has already been searched and returned sufficient records."],
            ),
            ToolSpec(
                id="inspect_context",
                runner="inspect_context",
                description="Return occurrence-level context examples already present in the evidence packet.",
                evidence_type="occurrence_context",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={"protein_id": "string optional"},
                output_schema={"examples": "list of occurrence context examples"},
                answers=["raw occurrence-level genomic context already present in the evidence packet"],
                cannot_answer=["candidate sequence motifs", "new homology search", "literature support"],
                required_artifacts=["occurrence_examples"],
                output_contract={"examples": "full hydrated occurrence context examples"},
                evidence_granularity="occurrence_context",
                when_to_use=["A hypothesis depends on genomic neighborhood structure or relative gene position."],
                when_not_to_use=["The relevant occurrence examples are already present in the context pack."],
            ),
            ToolSpec(
                id="summarize_annotations",
                runner="summarize_annotations",
                description="Summarize candidate-neighbor annotations from hydrated occurrence examples.",
                evidence_type="annotation_summary",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={},
                output_schema={"annotations": "list of candidate-neighbor annotation summaries"},
                answers=["candidate neighbor annotation summary across occurrence examples"],
                cannot_answer=[
                    "full genomic context feature presence",
                    "whether another neighboring protein such as Cas2 exists in the context",
                    "candidate sequence motif conservation",
                ],
                required_artifacts=["occurrence_examples"],
                output_contract={"annotations": "candidate-neighbor protein annotations only"},
                evidence_granularity="candidate_annotation",
                when_to_use=["The agent needs a compact view of candidate protein annotations across examples."],
                when_not_to_use=["The needed candidate annotations are already explicit in the evidence graph."],
            ),
            ToolSpec(
                id="query_context_features",
                runner="query_context_features",
                description="Search full occurrence-level genomic contexts for proteins matching annotation or cluster patterns.",
                evidence_type="full_context_feature_query",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={"patterns": "list of strings", "fields": "list of annotation fields optional"},
                output_schema={"matches": "list of occurrence context matches", "summary": "match counts"},
                answers=[
                    "full genomic context feature presence",
                    "whether a neighboring protein such as Cas2 exists in the context",
                    "relative position of matching context proteins",
                ],
                cannot_answer=["candidate sequence motif conservation", "new homology search", "literature support"],
                required_artifacts=["occurrence_context"],
                output_contract={"matches": "per-example proteins matching requested annotation or cluster patterns"},
                evidence_granularity="full_occurrence_context",
                when_to_use=[
                    "A falsification test asks whether a specific protein family, annotation, cluster, or neighbor exists in the full context."
                ],
                when_not_to_use=["The question is only about the candidate protein's own annotation."],
            ),
            ToolSpec(
                id="check_candidate_motifs",
                runner="check_candidate_motifs",
                description="Check candidate protein sequence for explicit residue or regex motif patterns.",
                evidence_type="candidate_motif_scan",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={"motifs": "list of {id, pattern} regex motifs"},
                output_schema={"motifs": "list of motif match reports"},
                answers=["candidate sequence motif presence", "explicit residue pattern presence"],
                cannot_answer=["structural conservation without a provided motif", "literature support", "genomic context"],
                required_artifacts=["candidate_protein_sequence"],
                output_contract={"motifs": "regex match positions using 1-based coordinates"},
                evidence_granularity="candidate_sequence",
                supports_dynamic_fallback=True,
                when_to_use=["The evidence need names explicit residue or motif patterns to check in the candidate sequence."],
                when_not_to_use=["No candidate protein sequence is available or the needed motif is not specified."],
            ),
            ToolSpec(
                id="local_sequence_architecture_probe",
                runner="local_sequence_architecture_probe",
                description="Scan the local DNA sequence window around the candidate for repeat-structure features.",
                evidence_type="local_sequence_architecture",
                cost_tier="cheap",
                estimated_runtime="seconds",
                input_schema={
                    "min_repeat_unit_length": "integer optional",
                    "max_repeat_unit_length": "integer optional",
                    "min_copy_count": "integer optional",
                },
                output_schema={"features": "list of repeat-structure features", "summary": "boolean and count summary"},
                answers=["repeat structure facts in the local DNA window", "repeat count summary"],
                cannot_answer=["candidate protein family naming", "literature support", "specific biological role labels"],
                required_artifacts=["candidate_dna_sequence"],
                output_contract={
                    "features": "repeat-structure inventory with coordinates and unit snippets",
                    "summary": "boolean and count summary without biological labels",
                },
                evidence_granularity="candidate_local_dna_window",
                when_to_use=["A hypothesis predicts informative repeat structure in the local locus DNA."],
                when_not_to_use=["No DNA sequence is available for the candidate-centered window."],
            ),
            ToolSpec(
                id="run_interproscan",
                runner="run_interproscan",
                description="Run InterProScan on the representative candidate-neighbor protein sequence.",
                evidence_type="candidate_domain_annotation",
                cost_tier="expensive",
                estimated_runtime="minutes",
                input_schema={"protein_id": "string optional", "force": "boolean optional"},
                output_schema={"trace": "external command trace", "domains": "tool-specific domain output optional"},
                answers=["candidate domain annotation", "InterPro/Pfam signature evidence for the candidate sequence"],
                cannot_answer=["full genomic context feature presence", "literature support"],
                required_artifacts=["candidate_protein_sequence"],
                output_contract={"trace": "external command trace", "domains": "parsed InterProScan records when available"},
                evidence_granularity="candidate_sequence",
                when_to_use=["Candidate-level domain evidence is missing or existing annotations need direct verification."],
                when_not_to_use=["Existing candidate Pfam or InterPro annotations already resolve the evidence need."],
            ),
            ToolSpec(
                id="run_candidate_mmseqs",
                runner="run_candidate_mmseqs",
                description="Search the representative candidate-neighbor protein against the configured MMseqs database.",
                evidence_type="candidate_homology",
                cost_tier="expensive",
                estimated_runtime="minutes",
                input_schema={
                    "protein_id": "string optional",
                    "max_hits": "integer optional",
                    "search_level": "integer optional",
                },
                output_schema={"hits": "list of parsed MMseqs hits", "trace": "external command trace"},
                answers=["candidate homology hit table", "candidate sequence similarity to database representatives"],
                cannot_answer=[
                    "conserved residue",
                    "catalytic motif",
                    "full genomic context feature presence",
                    "whether a neighboring protein such as Cas2 exists in the context",
                ],
                required_artifacts=["candidate_protein_sequence"],
                output_contract={
                    "hits": "parsed MMseqs hits without residue-level motif calls",
                    "trace": "external command trace",
                },
                evidence_granularity="candidate_sequence",
                when_to_use=["Candidate-level homology evidence is necessary and not already available."],
                when_not_to_use=["The candidate sequence is unavailable or equivalent homology evidence already exists."],
            ),
        ]
    )


def load_tool_manifest(path: Path | str | None, *, runner_ids: set[str]) -> ToolManifest:
    manifest = default_tool_manifest() if path is None else _read_tool_manifest(path)
    _validate_manifest(manifest, runner_ids=runner_ids)
    return manifest


def _read_tool_manifest(path: Path | str) -> ToolManifest:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ToolManifestError(f"Tool manifest must contain a mapping: {path}")
    try:
        return ToolManifest.model_validate(payload)
    except Exception as exc:
        raise ToolManifestError(f"Invalid tool manifest {path}: {exc}") from exc


def _validate_manifest(manifest: ToolManifest, *, runner_ids: set[str]) -> None:
    seen: set[str] = set()
    for tool in manifest.tools:
        if tool.id in seen:
            raise ToolManifestError(f"Duplicate tool id in manifest: {tool.id}")
        seen.add(tool.id)
        if tool.id != tool.runner:
            raise ToolManifestError(f"Tool manifest id {tool.id!r} must match runner {tool.runner!r}")
        if tool.runner not in runner_ids:
            raise ToolManifestError(f"Tool manifest runner {tool.runner!r} is not registered")
