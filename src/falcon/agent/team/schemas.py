from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class LiteratureQueryPlan(FlexibleModel):
    queries: list[str] = Field(min_length=1)
    rationale: str = ""


class LiteratureBrief(FlexibleModel):
    summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    citation_refs: list[str] = Field(default_factory=list)
    summaries: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_scoped_summaries(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("summaries"):
            return data
        if "summary" in data:
            return {
                **data,
                "summaries": [
                    {
                        "scope": "general",
                        "summary": data.get("summary", ""),
                        "key_findings": list(data.get("key_findings", []) or []),
                        "constraints": list(data.get("constraints", []) or []),
                        "citation_refs": list(data.get("citation_refs", []) or []),
                    }
                ],
            }
        return data


class HypothesisDraft(FlexibleModel):
    id: str
    claim: str = ""
    mechanism: str = ""
    expected_observations: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    mechanistic_label: str = ""
    role_level: str = ""
    why_it_matches: str = ""
    predicted_observations: list[str] = Field(default_factory=list)
    disconfirming_observations: list[str] = Field(default_factory=list)
    open_evidence_gaps: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_working_hypothesis_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if not normalized.get("claim") and normalized.get("mechanistic_label"):
            normalized["claim"] = normalized["mechanistic_label"]
        if not normalized.get("mechanistic_label") and normalized.get("claim"):
            normalized["mechanistic_label"] = normalized["claim"]
        if not normalized.get("predicted_observations") and normalized.get("expected_observations"):
            normalized["predicted_observations"] = normalized.get("expected_observations")
        if not normalized.get("disconfirming_observations") and normalized.get("alternative_explanations"):
            normalized["disconfirming_observations"] = normalized.get("alternative_explanations")
        if not normalized.get("why_it_matches") and normalized.get("mechanism"):
            normalized["why_it_matches"] = normalized.get("mechanism")
        return normalized


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


class ToolRequest(FlexibleModel):
    tool: str
    reason: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    evidence_need_id: str | None = None
    capability_match: str = ""
    expected_observation: str = ""
    why_existing_evidence_insufficient: str = ""

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


class DynamicToolDesign(FlexibleModel):
    evidence_need_id: str
    purpose: str
    input_artifacts: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    script_source: str
    limitations: list[str] = Field(default_factory=list)


class DynamicToolReview(FlexibleModel):
    approved: bool
    rationale: str
    required_changes: list[str] = Field(default_factory=list)


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
    supported_claim: dict[str, Any] = Field(default_factory=dict)
    working_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    next_evidence_plan: list[str] = Field(default_factory=list)
    accepted_hypotheses: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    unresolved_hypotheses: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
