from __future__ import annotations

from falcon.agent.team.ledger import (
    add_evidence_need_nodes,
    add_falsification_test_nodes,
    add_tool_observations,
    add_tool_request_nodes,
    add_tool_summary_nodes,
    initialize_ledger,
)
from falcon.agent.team.graph import EvidenceGraph

from test_agent_team import evidence_packet


def test_tool_summary_nodes_link_raw_observations_to_evidence_needs() -> None:
    ledger = initialize_ledger(candidate_index=1, candidate_slug="q1-neighbor30", evidence=evidence_packet())
    add_falsification_test_nodes(
        ledger,
        [
            {
                "id": "T1",
                "hypothesis_id": "H1",
                "question": "Is there direct candidate homology evidence?",
            }
        ],
        created_by="evidence_needs",
    )
    add_evidence_need_nodes(
        ledger,
        [
            {
                "id": "N1",
                "test_id": "T1",
                "evidence_needed": "candidate homology evidence",
            }
        ],
        created_by="evidence_needs",
    )
    add_tool_request_nodes(
        ledger,
        [
            {
                "tool": "run_candidate_mmseqs",
                "reason": "Need direct homology evidence.",
                "evidence_need_id": "N1",
            }
        ],
        created_by="tool_planner",
    )
    add_tool_observations(
        ledger,
        [
            {
                "tool": "run_candidate_mmseqs",
                "status": "ok",
                "hits": [{"target_id": "rep1", "bits": 120.0}],
                "request_id": "tool_request:1",
            }
        ],
    )
    add_tool_summary_nodes(
        ledger,
        [
            {
                "tool": "run_candidate_mmseqs",
                "status": "ok",
                "lifecycle": "active",
                "summary_type": "candidate_homology",
                "request_id": "tool_request:1",
                "raw_observation_ref": "TOOL:run_candidate_mmseqs:1",
                "addresses": ["N1"],
                "summary": {"top_hit_count": 1},
            }
        ],
        created_by="tool_scheduler",
    )

    graph = EvidenceGraph.from_dict(ledger["evidence_graph"]).to_dict()
    assert any(node["type"] == "tool_summary" for node in graph["nodes"])
    assert any(
        edge["type"] == "derived_from"
        and edge["source"] == "tool_summary:1"
        and edge["target"] == "tool_observation:1"
        for edge in graph["edges"]
    )
    assert any(
        edge["type"] == "addresses"
        and edge["source"] == "tool_summary:1"
        and edge["target"] == "evidence_need:1"
        for edge in graph["edges"]
    )

