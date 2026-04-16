from __future__ import annotations

from pathlib import Path
import json

from falcon.agent.providers import ScriptedLLMProvider
from falcon.agent.team import load_team_role_instructions, run_team_loop
from falcon.literature.search import LiteratureRecord, StaticLiteratureClient
from falcon.tools.dynamic import DynamicPythonToolRunner
from falcon.tools.agent_registry import EvidenceToolExecutor
from falcon.tools.manifest import default_tool_manifest


def evidence_packet() -> dict:
    return {
        "candidate": {
            "query_id": "q1",
            "cluster_30": "neighbor30",
            "fold_enrichment": 16.0,
            "q_value": 0.01,
            "presence_contexts": 4,
            "query_contexts": 5,
        },
        "examples": [
            {
                "context_protein_id": "target1",
                "neighbor_protein_id": "neighbor1",
                "neighbor_protein": {
                    "protein_id": "neighbor1",
                    "product": "hypothetical protein",
                    "pfam": None,
                    "interpro": None,
                },
                "neighbor_clusters": {"30": "neighbor30"},
                "relative_index": 1,
            }
        ],
        "sequence_evidence": {
            "protein": {"available": True, "protein_id": "neighbor1", "sequence": "MKT"},
            "dna": {"available": True},
        },
        "deterministic_checks": [
            {
                "question": "Is co-localization statistically supported?",
                "status": "pass",
                "evidence": "q_value=0.01",
            }
        ],
        "uncertainties": [],
    }


def scripted_deep_loop_provider() -> ScriptedLLMProvider:
    return ScriptedLLMProvider(
        [
            {"queries": ["CRISPR accessory protein hypothetical"], "rationale": "Ground the candidate in CRISPR literature."},
            {
                "summary": "CRISPR accessory proteins require direct domain or homology support before naming.",
                "key_findings": ["Co-localization alone does not prove function."],
                "constraints": ["Do not infer candidate function from neighbor annotations."],
                "citation_refs": ["L1"],
            },
            {
                "hypotheses": [
                    {
                        "id": "H1",
                        "claim": "The candidate may be a CRISPR-proximal accessory protein.",
                        "mechanism": "Unknown protein near a seed system may participate in local immunity.",
                        "expected_observations": ["direct homologs or domains in CRISPR-associated proteins"],
                        "alternative_explanations": ["passenger gene near CRISPR locus"],
                        "evidence_refs": ["L1"],
                    }
                ]
            },
            {
                "tests": [
                    {
                        "id": "T1",
                        "hypothesis_id": "H1",
                        "question": "Does the candidate itself have direct CRISPR-associated homology or domains?",
                        "support_criteria": "Candidate MMseqs or InterProScan returns CRISPR-associated hits/domains.",
                        "weaken_criteria": "Only weak generic or hypothetical hits are found.",
                        "falsify_criteria": "Strong non-CRISPR domains explain the protein.",
                        "evidence_needed": "direct candidate protein homology/domain evidence",
                        "suggested_tools": ["run_candidate_mmseqs", "run_interproscan"],
                    }
                ]
            },
            {
                "tool_requests": [
                    {
                        "tool": "run_candidate_mmseqs",
                        "reason": "Need direct homology evidence for the candidate protein itself.",
                        "parameters": {"protein_id": "neighbor1", "max_hits": 3},
                    },
                    {
                        "tool": "run_interproscan",
                        "reason": "Need direct domain evidence.",
                        "parameters": {"protein_id": "neighbor1", "force": True},
                    },
                ],
                "skipped_needs": [],
            },
            {
                "audits": [
                    {
                        "test_id": "T1",
                        "hypothesis_id": "H1",
                        "verdict": "support",
                        "rationale": "Direct tools returned CRISPR-adjacent weak evidence, but not a named function.",
                        "evidence_refs": ["TOOL:run_candidate_mmseqs:1", "TOOL:run_interproscan:2"],
                        "contradictions": [],
                    }
                ]
            },
            {
                "revised_hypotheses": [
                    {
                        "id": "H1",
                        "version": 2,
                        "claim": "The candidate is a weak CRISPR-proximal accessory candidate, not a named Cas protein.",
                        "status": "retained",
                        "rationale": "Direct evidence is weak and does not justify a specific function.",
                    }
                ],
                "rejected_hypotheses": [],
                "contradictions": [],
            },
            {
                "status": "weak",
                "rationale": "The candidate remains a weak accessory candidate after literature grounding and direct tools.",
                "evidence_refs": ["L1", "T1", "TOOL:run_candidate_mmseqs:1"],
                "accepted_hypotheses": ["H1"],
                "rejected_hypotheses": [],
                "unresolved_hypotheses": [],
                "uncertainties": ["No specific biochemical role is supported."],
            },
        ]
    )


def test_team_loop_builds_candidate_ledger_with_literature_and_direct_tools() -> None:
    executor = EvidenceToolExecutor(
        literature_client=StaticLiteratureClient(
            [
                LiteratureRecord(
                    source="pubmed",
                    title="CRISPR accessory proteins require direct evidence",
                    abstract="Direct domain and homology evidence is needed.",
                    pmid="42",
                )
            ]
        ),
        interproscan_runner=lambda request, evidence: {
            "tool": "run_interproscan",
            "status": "ok",
            "protein_id": request["parameters"]["protein_id"],
            "evidence_ref": "TOOL:run_interproscan:2",
            "domains": [],
        },
        mmseqs_runner=lambda request, evidence: {
            "tool": "run_candidate_mmseqs",
            "status": "ok",
            "protein_id": request["parameters"]["protein_id"],
            "evidence_ref": "TOOL:run_candidate_mmseqs:1",
            "hits": [{"target_id": "crispr_hit", "bits": 50.0}],
        },
    )

    result = run_team_loop(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        evidence=evidence_packet(),
        provider=scripted_deep_loop_provider(),
        tool_executor=executor,
        max_rounds=1,
    )

    ledger = result.ledger
    assert result.reasoning["status"] == "weak"
    assert result.team_trace["workflow"] == "team"
    assert [call["role"] for call in result.role_calls][:2] == [
        "literature_scout_queries",
        "literature_scout_brief",
    ]
    assert ledger["literature"]["records"][0]["pmid"] == "42"
    assert ledger["literature"]["brief"]["citation_refs"] == ["L1"]
    assert ledger["hypotheses"][0]["id"] == "H1"
    assert ledger["falsification_tests"][0]["hypothesis_id"] == "H1"
    assert ledger["falsification_tests"][0]["question"].startswith("Does the candidate itself")
    direct_tool_names = [
        item["tool"]
        for item in ledger["tool_observations"]
        if item["tool"] in {"run_candidate_mmseqs", "run_interproscan"}
    ]
    assert direct_tool_names == [
        "run_candidate_mmseqs",
        "run_interproscan",
    ]
    assert ledger["audit"]["findings"][0]["verdict"] == "support"
    assert ledger["final"]["accepted_hypotheses"] == ["H1"]


def test_team_loop_records_invalid_tool_plan_as_validation_rejection() -> None:
    provider = ScriptedLLMProvider(
        [
            {"queries": ["CRISPR candidate"], "rationale": "Ground literature."},
            {"summary": "No strong literature.", "key_findings": [], "constraints": [], "citation_refs": []},
            {
                "hypotheses": [
                    {
                        "id": "H1",
                        "claim": "Candidate.",
                        "mechanism": "Unknown.",
                        "expected_observations": ["direct evidence"],
                        "alternative_explanations": ["passenger"],
                        "evidence_refs": [],
                    }
                ]
            },
            {
                "tests": [
                    {
                        "id": "T1",
                        "hypothesis_id": "H1",
                        "question": "Need direct evidence?",
                        "support_criteria": "direct hit",
                        "weaken_criteria": "weak hit",
                        "falsify_criteria": "contradictory hit",
                        "evidence_needed": "direct evidence",
                        "suggested_tools": ["run_candidate_mmseqs"],
                    }
                ]
            },
            {"tool_requests": [{"tool": "interproscan", "parameters": {"protein_id": "neighbor1"}}]},
            {
                "audits": [
                    {
                        "test_id": "T1",
                        "hypothesis_id": "H1",
                        "verdict": "unresolved",
                        "rationale": "The requested tool was rejected before execution.",
                        "evidence_refs": [],
                        "contradictions": ["tool plan used a tool id absent from the manifest"],
                    }
                ]
            },
            {
                "revised_hypotheses": [
                    {
                        "id": "H1",
                        "version": 2,
                        "claim": "Candidate remains unresolved.",
                        "status": "unresolved",
                        "rationale": "Evidence collection failed validation.",
                    }
                ],
                "rejected_hypotheses": [],
                "contradictions": ["tool plan used a tool id absent from the manifest"],
            },
            {"status": "incomplete", "rationale": "Invalid tool plan left evidence unresolved.", "evidence_refs": [], "uncertainties": []},
        ]
    )

    result = run_team_loop(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        evidence=evidence_packet(),
        provider=provider,
        tool_executor=EvidenceToolExecutor(),
        max_rounds=1,
        schema_retries=1,
    )

    assert result.reasoning["status"] == "incomplete"
    assert "blocked_step" not in result.ledger
    assert result.ledger["tool_plan_validations"][0]["status"] == "rejected"
    assert any(observation["status"] == "rejected" for observation in result.ledger["tool_observations"])
    assert result.role_calls[-1]["role"] == "synthesizer"


def test_team_loop_writes_replayable_role_payloads() -> None:
    result = run_team_loop(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        evidence=evidence_packet(),
        provider=scripted_deep_loop_provider(),
        tool_executor=EvidenceToolExecutor(
            literature_client=StaticLiteratureClient(
                [LiteratureRecord(source="pubmed", title="CRISPR accessory evidence", pmid="1")]
            ),
            interproscan_runner=lambda request, evidence: {"tool": "run_interproscan", "status": "ok"},
            mmseqs_runner=lambda request, evidence: {"tool": "run_candidate_mmseqs", "status": "ok"},
        ),
        max_rounds=1,
    )

    encoded = [json.dumps(record, sort_keys=True) for record in result.role_calls]
    assert all("messages" in record for record in result.role_calls)
    assert any("literature_scout" in record for record in encoded)


def test_team_prompt_loader_includes_context_requirements_and_antipatterns(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "team_prompts"
    prompt_dir.mkdir()
    for role in (
        "literature_scout",
        "hypothesis_generator",
        "evidence_needs",
        "tool_planner",
        "evidence_auditor",
        "hypothesis_reviser",
        "synthesizer",
    ):
        prompt_dir.joinpath(f"{role}.yaml").write_text(
            f"""
role: {role}
system: System text.
developer_guidance: Developer text.
context_requirements:
  - Read candidate_context.representative_neighbor before making candidate claims.
few_shot_antipatterns:
  - Do not convert neighbor Cas9 annotation into a candidate protein function.
output_contract: Output text.
""",
            encoding="utf-8",
        )

    instructions = load_team_role_instructions(prompt_dir)

    tool_planner_prompt = instructions["tool_planner"]
    assert "Context requirements:" in tool_planner_prompt
    assert "candidate_context.representative_neighbor" in tool_planner_prompt
    assert "Anti-patterns:" in tool_planner_prompt
    assert "neighbor Cas9 annotation" in tool_planner_prompt


def test_team_prompt_loader_loads_repository_prompt_pack() -> None:
    instructions = load_team_role_instructions("prompts/agent/team")

    assert "context_workbench" in instructions["tool_planner"]
    assert "run_candidate_mmseqs" not in instructions["tool_planner"]
    assert "run_interproscan" not in instructions["tool_planner"]
    assert "candidate protein evidence" in instructions["hypothesis_generator"]


def test_team_loop_sends_context_pack_and_records_role_outputs_in_graph() -> None:
    result = run_team_loop(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        evidence=evidence_packet(),
        provider=scripted_deep_loop_provider(),
        tool_executor=EvidenceToolExecutor(
            literature_client=StaticLiteratureClient(
                [LiteratureRecord(source="pubmed", title="CRISPR accessory evidence", pmid="1")]
            ),
            interproscan_runner=lambda request, evidence: {"tool": "run_interproscan", "status": "ok"},
            mmseqs_runner=lambda request, evidence: {"tool": "run_candidate_mmseqs", "status": "ok"},
        ),
        max_rounds=1,
        tool_manifest=default_tool_manifest(),
    )

    planner_call = next(call for call in result.role_calls if call["role"] == "tool_planner")
    planner_payload = json.loads(planner_call["messages"][1]["content"])

    assert planner_payload["role"] == "tool_planner"
    assert planner_payload["candidate_context"]["representative_neighbor"]["protein_id"] == "neighbor1"
    assert {tool["id"] for tool in planner_payload["context_workbench"]["tool_catalog"]} >= {
        "run_candidate_mmseqs",
        "run_interproscan",
    }
    graph = result.ledger["evidence_graph"]
    node_types = [node["type"] for node in graph["nodes"]]
    assert "literature_record" in node_types
    assert "hypothesis" in node_types
    assert "falsification_test" in node_types
    assert "evidence_need" in node_types
    assert "tool_request" in node_types
    assert "tool_observation" in node_types
    assert "audit_finding" in node_types
    assert "revision" in node_types
    assert "final_claim" in node_types


def test_team_loop_can_run_reviewed_dynamic_tool_fallback(tmp_path: Path) -> None:
    provider = ScriptedLLMProvider(
        [
            {"queries": ["candidate local check"], "rationale": "Ground the candidate."},
            {"summary": "No direct literature.", "key_findings": [], "constraints": [], "citation_refs": []},
            {
                "hypotheses": [
                    {
                        "id": "H1",
                        "claim": "Candidate requires a local custom evidence check.",
                        "mechanism": "Unknown.",
                        "expected_observations": ["custom local evidence"],
                        "alternative_explanations": ["passenger"],
                        "evidence_refs": [],
                    }
                ]
            },
            {
                "tests": [
                    {
                        "id": "T1",
                        "hypothesis_id": "H1",
                        "question": "Can a local custom check be computed?",
                        "support_criteria": "Dynamic tool returns a structured observation.",
                        "weaken_criteria": "Dynamic tool is inconclusive.",
                        "falsify_criteria": "Dynamic tool contradicts the claim.",
                        "evidence_needed": "custom local evidence unsupported by fixed tools",
                        "suggested_tools": [],
                    }
                ]
            },
            {
                "tool_requests": [
                    {
                        "tool": "not_in_manifest",
                        "evidence_need_id": "T1",
                        "reason": "No fixed manifest tool can compute this local check.",
                        "parameters": {},
                    }
                ],
                "skipped_needs": [],
            },
            {
                "evidence_need_id": "T1",
                "purpose": "Compute a local structured observation from the provided input bundle.",
                "input_artifacts": ["target_evidence_need"],
                "output_schema": {"answer": "string"},
                "script_source": (
                    "def run(input_payload):\n"
                    "    return {\n"
                    "        'status': 'ok',\n"
                    "        'answer': input_payload['target_evidence_need']['test_id'],\n"
                    "        'observations': [{'computed': True}],\n"
                    "        'evidence_refs': [],\n"
                    "        'limitations': []\n"
                    "    }\n"
                ),
                "limitations": [],
            },
            {"approved": True, "rationale": "The script is local, read-only, and returns structured JSON.", "required_changes": []},
            {
                "audits": [
                    {
                        "test_id": "T1",
                        "hypothesis_id": "H1",
                        "verdict": "support",
                        "rationale": "The dynamic tool returned a structured observation.",
                        "evidence_refs": [],
                        "contradictions": [],
                    }
                ]
            },
            {
                "revised_hypotheses": [
                    {
                        "id": "H1",
                        "version": 2,
                        "claim": "Candidate has a computed local observation.",
                        "status": "retained",
                        "rationale": "Dynamic evidence was collected.",
                    }
                ],
                "rejected_hypotheses": [],
                "contradictions": [],
            },
            {
                "status": "weak",
                "rationale": "Dynamic evidence was collected and audited.",
                "evidence_refs": [],
                "accepted_hypotheses": ["H1"],
                "rejected_hypotheses": [],
                "unresolved_hypotheses": [],
                "uncertainties": [],
            },
        ]
    )

    result = run_team_loop(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        evidence=evidence_packet(),
        provider=provider,
        tool_executor=EvidenceToolExecutor(),
        max_rounds=1,
        dynamic_tools_enabled=True,
        dynamic_tool_runner=DynamicPythonToolRunner(output_dir=tmp_path / "dynamic", log_dir=tmp_path / "logs"),
    )

    assert result.ledger["dynamic_tools"][-1]["result"]["result"]["answer"] == "T1"
    assert any(node["type"] == "dynamic_tool_result" for node in result.ledger["evidence_graph"]["nodes"])
    assert any(observation.get("tool") == "dynamic_python" for observation in result.ledger["tool_observations"])
