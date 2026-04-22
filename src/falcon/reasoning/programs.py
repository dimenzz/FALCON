from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProgramType = Literal[
    "identity_adjudication",
    "semantic_bridge_resolution",
    "local_context_discrimination",
    "cohort_anomaly_scan",
    "subgroup_comparison",
    "literature_regrounding",
    "architecture_comparison",
    "cross_system_comparison",
    "defer_unresolved",
]


class ProgramStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    step_id: str
    program_type: ProgramType
    goal: str
    why_now: str = ""
    inputs_required: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    branch_conditions: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    focus_terms: list[str] = Field(default_factory=list)


class ResearchAgenda(BaseModel):
    model_config = ConfigDict(extra="allow")

    main_question: str
    current_program: str
    steps: list[ProgramStep] = Field(min_length=1, max_length=4)


class RuntimeSynthesis(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    rationale: str
    supported_claim: dict = Field(default_factory=dict)
    notebook_summary: list[str] = Field(default_factory=list)
    agenda_summary: list[str] = Field(default_factory=list)
    next_program_recommendations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
