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
                when_to_use=["The agent needs a compact view of candidate protein annotations across examples."],
                when_not_to_use=["The needed candidate annotations are already explicit in the evidence graph."],
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
                when_to_use=["Candidate-level domain evidence is missing or existing annotations need direct verification."],
                when_not_to_use=["Existing candidate Pfam/InterPro annotations already resolve the evidence need."],
            ),
            ToolSpec(
                id="run_candidate_mmseqs",
                runner="run_candidate_mmseqs",
                description="Search the representative candidate-neighbor protein against the configured MMseqs database.",
                evidence_type="candidate_homology",
                cost_tier="expensive",
                estimated_runtime="minutes",
                input_schema={"protein_id": "string optional", "max_hits": "integer optional", "search_level": "integer optional"},
                output_schema={"hits": "list of parsed MMseqs hits", "trace": "external command trace"},
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
