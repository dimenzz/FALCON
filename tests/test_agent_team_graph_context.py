from falcon.agent.team.context_pack import build_role_context_pack
from falcon.agent.team.graph import EvidenceGraph
from falcon.agent.team.ledger import initialize_ledger
from falcon.tools.manifest import ToolManifest, ToolSpec

from test_agent_team import evidence_packet


def test_evidence_graph_records_nodes_edges_and_provenance() -> None:
    graph = EvidenceGraph()

    hypothesis_node = graph.add_node(
        "hypothesis",
        {"id": "H1", "claim": "Candidate may be CRISPR-proximal."},
        created_by="hypothesis_generator",
    )
    observation_node = graph.add_node(
        "tool_observation",
        {"tool": "run_candidate_mmseqs", "status": "ok"},
        created_by="tool_scheduler",
    )
    graph.add_edge(
        observation_node,
        hypothesis_node,
        "supports",
        created_by="evidence_auditor",
        payload={"test_id": "T1"},
    )

    payload = graph.to_dict()
    assert payload["nodes"][0]["id"] == "hypothesis:1"
    assert payload["nodes"][0]["created_by"] == "hypothesis_generator"
    assert payload["nodes"][1]["id"] == "tool_observation:1"
    assert payload["edges"] == [
        {
            "id": "edge:1",
            "source": "tool_observation:1",
            "target": "hypothesis:1",
            "type": "supports",
            "payload": {"test_id": "T1"},
            "created_by": "evidence_auditor",
        }
    ]


def test_tool_planner_context_pack_contains_candidate_evidence_graph_and_manifest() -> None:
    evidence = evidence_packet()
    ledger = initialize_ledger(candidate_index=1, candidate_slug="q1-neighbor30", evidence=evidence)
    graph = EvidenceGraph.from_dict(ledger["evidence_graph"])
    graph.add_node(
        "evidence_need",
        {"test_id": "T1", "evidence_needed": "direct candidate homology evidence"},
        created_by="evidence_needs",
    )
    ledger["evidence_graph"] = graph.to_dict()
    manifest = ToolManifest(
        tools=[
            ToolSpec(
                id="run_candidate_mmseqs",
                runner="run_candidate_mmseqs",
                description="Search the candidate protein against the configured MMseqs database.",
                evidence_type="candidate_homology",
                cost_tier="expensive",
                estimated_runtime="minutes",
                enabled=True,
                input_schema={"protein_id": "string"},
                output_schema={"hits": "list"},
                when_to_use=["Candidate-level homology evidence is missing."],
                when_not_to_use=["Equivalent direct candidate homology evidence is already available."],
            )
        ]
    )

    pack = build_role_context_pack(
        role="tool_planner",
        ledger=ledger,
        evidence=evidence,
        tool_manifest=manifest,
    )

    assert pack["role"] == "tool_planner"
    assert pack["candidate_context"]["candidate"]["cluster_30"] == "neighbor30"
    assert pack["candidate_context"]["representative_neighbor"]["protein_id"] == "neighbor1"
    assert pack["candidate_context"]["representative_neighbor"]["product"] == "hypothetical protein"
    assert pack["candidate_context"]["evidence_boundary"] == (
        "candidate_neighbor_protein_is_not_the_seed_or_context_query_protein"
    )
    assert pack["evidence_graph"]["nodes"][0]["type"] == "candidate"
    assert pack["evidence_graph"]["nodes"][-1]["type"] == "evidence_need"
    assert pack["tool_manifest"][0]["id"] == "run_candidate_mmseqs"
    assert pack["tool_manifest"][0]["cost_tier"] == "expensive"
    assert pack["context_workbench"]["tool_catalog"][0]["id"] == "run_candidate_mmseqs"
    assert "data_contracts" in pack["context_workbench"]
    assert "artifact_index" in pack["context_workbench"]
    assert pack["context_workbench"]["context_views"]["candidate_identity"]["protein_id"] == "neighbor1"
    assert pack["context_workbench"]["dynamic_tool_contract"]["script_contract"] == (
        "define run(input_payload: dict) -> dict"
    )
