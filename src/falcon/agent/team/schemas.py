from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class LiteratureQueryPlan(FlexibleModel):
    queries: list[str] = Field(min_length=1)
    rationale: str = ""


class LiteratureBrief(FlexibleModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)


class HypothesisDraft(FlexibleModel):
    id: str
    claim: str
    mechanism: str = ""
    expected_observations: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class HypothesisSet(FlexibleModel):
    hypotheses: list[HypothesisDraft] = Field(min_length=1)


class FalsificationTest(FlexibleModel):
    id: str
    hypothesis_id: str
    question: str
    support_criteria: str
    weaken_criteria: str
    falsify_criteria: str
    evidence_needed: str
    suggested_tools: list[str] = Field(default_factory=list)


class EvidenceNeeds(FlexibleModel):
    tests: list[FalsificationTest] = Field(min_length=1)


AllowedToolName = Literal[
    "search_literature",
    "inspect_context",
    "summarize_annotations",
    "run_interproscan",
    "run_candidate_mmseqs",
]


class ToolRequest(FlexibleModel):
    tool: AllowedToolName
    reason: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _move_legacy_arguments(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "parameters" in data:
            return data
        parameters = {
            key: value
            for key, value in data.items()
            if key not in {"tool", "reason", "rationale"}
        }
        normalized = dict(data)
        if parameters:
            normalized["parameters"] = parameters
        return normalized


class SkippedEvidenceNeed(FlexibleModel):
    evidence_needed: str
    reason: str


class ToolPlan(FlexibleModel):
    tool_requests: list[ToolRequest] = Field(default_factory=list)
    skipped_needs: list[SkippedEvidenceNeed] = Field(default_factory=list)


class AuditFinding(FlexibleModel):
    test_id: str
    hypothesis_id: str
    verdict: Literal["support", "weaken", "falsify", "unresolved", "conflicting"]
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class AuditReport(FlexibleModel):
    audits: list[AuditFinding] = Field(default_factory=list)


class RevisedHypothesis(FlexibleModel):
    id: str
    version: int = 2
    claim: str
    status: Literal["retained", "revised", "rejected", "merged", "unresolved"] = "revised"
    rationale: str = ""


class RejectedHypothesis(FlexibleModel):
    id: str
    reason: str


class HypothesisRevision(FlexibleModel):
    revised_hypotheses: list[RevisedHypothesis] = Field(default_factory=list)
    rejected_hypotheses: list[RejectedHypothesis] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


class SynthesisResult(FlexibleModel):
    status: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    accepted_hypotheses: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    unresolved_hypotheses: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
