from falcon.tools.agent_registry import EvidenceToolExecutor
from falcon.tools.manifest import ToolManifest, ToolSpec

from test_agent_team import evidence_packet


def test_tool_executor_skips_disabled_manifest_tool() -> None:
    manifest = ToolManifest(
        tools=[
            ToolSpec(
                id="run_candidate_mmseqs",
                runner="run_candidate_mmseqs",
                description="Disabled candidate homology search.",
                evidence_type="candidate_homology",
                cost_tier="expensive",
                estimated_runtime="minutes",
                enabled=False,
            )
        ]
    )
    executor = EvidenceToolExecutor(tool_manifest=manifest)

    results, _ = executor.execute_requests(
        [{"tool": "run_candidate_mmseqs", "parameters": {"protein_id": "neighbor1"}}],
        evidence_packet(),
    )

    assert results == [
        {
            "tool": "run_candidate_mmseqs",
            "status": "skipped",
            "reason": "tool is disabled by manifest",
        }
    ]


def test_tool_executor_defers_expensive_tools_after_budget_is_exhausted() -> None:
    manifest = ToolManifest(
        tools=[
            ToolSpec(
                id="run_candidate_mmseqs",
                runner="run_candidate_mmseqs",
                description="Candidate homology search.",
                evidence_type="candidate_homology",
                cost_tier="expensive",
                estimated_runtime="minutes",
                enabled=True,
            )
        ]
    )
    calls = []
    executor = EvidenceToolExecutor(
        tool_manifest=manifest,
        max_expensive_tools_per_candidate=1,
        mmseqs_runner=lambda request, evidence: calls.append(request) or {"tool": "run_candidate_mmseqs", "status": "ok"},
    )

    results, _ = executor.execute_requests(
        [
            {"tool": "run_candidate_mmseqs", "parameters": {"protein_id": "neighbor1", "max_hits": 1}},
            {"tool": "run_candidate_mmseqs", "parameters": {"protein_id": "neighbor1", "max_hits": 2}},
        ],
        evidence_packet(),
    )

    assert [result["status"] for result in results] == ["ok", "deferred"]
    assert results[1]["reason"] == "expensive tool budget exhausted"
    assert len(calls) == 1
