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


def test_query_context_features_searches_full_occurrence_context() -> None:
    evidence = evidence_packet()
    evidence["examples"][0]["context"] = {
        "context": [
            {
                "relative_index": 0,
                "protein": {
                    "protein_id": "seed1",
                    "product": "CRISPR-associated endonuclease Cas9",
                    "gene_name": "cas9",
                    "pfam": "PF16595",
                    "interpro": "IPR003615",
                },
                "clusters": {"30": "seed30"},
            },
            {
                "relative_index": 2,
                "protein": {
                    "protein_id": "cas2a",
                    "product": "CRISPR-associated endoribonuclease Cas2",
                    "gene_name": "cas2",
                    "pfam": "PF09827",
                    "interpro": "IPR019199",
                },
                "clusters": {"30": "cas2cluster"},
            },
        ]
    }
    executor = EvidenceToolExecutor()

    results, _ = executor.execute_requests(
        [{"tool": "query_context_features", "parameters": {"patterns": ["Cas2", "PF09827"]}}],
        evidence,
    )

    assert results[0]["status"] == "ok"
    assert results[0]["summary"]["contexts_with_matches"] == 1
    assert results[0]["matches"][0]["matches"][0]["protein_id"] == "cas2a"


def test_check_candidate_motifs_reports_candidate_sequence_matches() -> None:
    evidence = evidence_packet()
    evidence["sequence_evidence"]["protein"]["sequence"] = "MADDKTD"
    executor = EvidenceToolExecutor()

    results, _ = executor.execute_requests(
        [{"tool": "check_candidate_motifs", "parameters": {"motifs": [{"id": "acidic_pair", "pattern": "D.K"}]}}],
        evidence,
    )

    assert results[0]["status"] == "ok"
    assert results[0]["motifs"][0]["id"] == "acidic_pair"
    assert results[0]["motifs"][0]["matches"][0]["start"] == 3


def test_local_sequence_architecture_probe_reports_repeat_inventory_and_boolean_count_summary() -> None:
    evidence = evidence_packet()
    evidence["sequence_evidence"]["dna"]["sequence"] = "ATGCGGTTATGCGGTTCCCAAATGCGGTT"
    executor = EvidenceToolExecutor()

    results, _ = executor.execute_requests(
        [
            {
                "tool": "local_sequence_architecture_probe",
                "parameters": {"min_repeat_unit_length": 4, "max_repeat_unit_length": 8, "min_copy_count": 2},
            }
        ],
        evidence,
    )

    assert results[0]["status"] == "ok"
    assert results[0]["features"]
    assert results[0]["features"][0]["feature_type"] in {"direct_repeat", "periodic_repeat_array", "inverted_repeat"}
    assert "consensus_or_unit_snippet" in results[0]["features"][0]
    assert "repeat_feature_count" in results[0]["summary"]
    assert "direct_repeat_present" in results[0]["summary"]
