from pathlib import Path

import pytest

from falcon.tools.manifest import ToolManifestError, load_tool_manifest
from falcon.tools.plan_validator import ToolPlanValidator


def test_tool_manifest_loads_prompt_payload_and_validates_runner_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool_manifest.yaml"
    manifest_path.write_text(
        """
tools:
  - id: run_candidate_mmseqs
    runner: run_candidate_mmseqs
    description: Search the candidate protein against the configured MMseqs database.
    evidence_type: candidate_homology
    cost_tier: expensive
    estimated_runtime: minutes
    enabled: true
    input_schema:
      protein_id: string
    output_schema:
      hits: list
    when_to_use:
      - Candidate-level homology evidence is missing.
    when_not_to_use:
      - Existing direct homology evidence already resolves the evidence need.
""",
        encoding="utf-8",
    )

    manifest = load_tool_manifest(manifest_path, runner_ids={"run_candidate_mmseqs"})

    prompt_payload = manifest.to_prompt_payload()
    assert prompt_payload == [
        {
            "id": "run_candidate_mmseqs",
            "description": "Search the candidate protein against the configured MMseqs database.",
            "evidence_type": "candidate_homology",
            "cost_tier": "expensive",
            "estimated_runtime": "minutes",
            "enabled": True,
            "input_schema": {"protein_id": "string"},
            "output_schema": {"hits": "list"},
            "answers": [],
            "cannot_answer": [],
            "required_artifacts": [],
            "output_contract": {},
            "evidence_granularity": "unspecified",
            "examples": [],
            "supports_dynamic_fallback": False,
            "when_to_use": ["Candidate-level homology evidence is missing."],
            "when_not_to_use": ["Existing direct homology evidence already resolves the evidence need."],
        }
    ]


def test_tool_manifest_rejects_tools_without_matching_runner(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool_manifest.yaml"
    manifest_path.write_text(
        """
tools:
  - id: interproscan
    runner: interproscan
    description: Wrong legacy name.
    evidence_type: domains
    cost_tier: expensive
    estimated_runtime: minutes
    enabled: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ToolManifestError, match="interproscan"):
        load_tool_manifest(manifest_path, runner_ids={"run_interproscan"})


def test_tool_plan_validator_rejects_manifest_capability_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool_manifest.yaml"
    manifest_path.write_text(
        """
tools:
  - id: run_candidate_mmseqs
    runner: run_candidate_mmseqs
    description: Search candidate homology.
    evidence_type: candidate_homology
    answers:
      - candidate homology hit table
    cannot_answer:
      - conserved residue
      - catalytic motif
    output_contract:
      hits: parsed MMseqs hits without residue-level motif calls
""",
        encoding="utf-8",
    )
    manifest = load_tool_manifest(manifest_path, runner_ids={"run_candidate_mmseqs"})

    accepted, validations = ToolPlanValidator(manifest).validate(
        [
            {
                "tool": "run_candidate_mmseqs",
                "evidence_need_id": "test_cas1_catalytic_residues",
                "reason": "Check conserved residue conservation in the candidate.",
            }
        ],
        evidence_needs=[
            {
                "test_id": "test_cas1_catalytic_residues",
                "evidence_needed": "Determine whether conserved residue and catalytic motif are present.",
            }
        ],
    )

    assert accepted == []
    assert validations == [
        {
            "tool": "run_candidate_mmseqs",
            "evidence_need_id": "test_cas1_catalytic_residues",
            "status": "rejected",
            "reason": "tool capability mismatch: conserved residue; catalytic motif",
        }
    ]
