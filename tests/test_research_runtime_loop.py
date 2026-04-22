from pathlib import Path

from falcon.agent.providers import ScriptedLLMProvider
from falcon.reasoning.runtime import run_research_runtime
from falcon.tools.accession_enrichment import AccessionEnricher
from falcon.tools.agent_registry import EvidenceToolExecutor


class FailingLiteratureClient:
    def search(self, query: str, max_results: int):  # noqa: ANN001
        raise RuntimeError("literature backend unavailable")


def _runtime_inputs() -> dict:
    return {
        "candidate_summary": {
            "query_id": "q1",
            "cluster_30": "neighbor30",
            "presence_contexts": 4,
            "query_contexts": 5,
            "fold_enrichment": 16.0,
            "q_value": 0.01,
        },
        "seed_summary": {
            "query_id": "q1",
            "query_prior": {
                "query_id": "q1",
                "function_description": "SpCas9 seed protein",
                "confidence": "soft_prior",
            },
            "target_consensus_annotation": {
                "product": "CRISPR-associated endonuclease Cas9",
                "gene_name": "cas9",
                "pfam": "PF01867",
            },
            "note": "Seed query descriptions are soft priors.",
        },
        "candidate_neighbor_summary": {
            "protein_id": "neighbor1",
            "product": "hypothetical protein",
            "pfam": None,
            "interpro": None,
            "kegg": None,
            "cog_id": None,
        },
        "occurrence_bundle": {
            "examples": [
                {
                    "context_protein_id": "target1",
                    "neighbor_protein_id": "neighbor1",
                    "context": {
                        "target": {
                            "protein_id": "target1",
                            "product": "CRISPR-associated endonuclease Cas9",
                            "gene_name": "cas9",
                        },
                        "context": [
                            {
                                "relative_index": 0,
                                "is_target": True,
                                "protein": {
                                    "protein_id": "target1",
                                    "product": "CRISPR-associated endonuclease Cas9",
                                },
                                "clusters": {"30": "seed30"},
                            },
                            {
                                "relative_index": 1,
                                "protein": {
                                    "protein_id": "neighbor1",
                                    "product": "hypothetical protein",
                                },
                                "clusters": {"30": "neighbor30"},
                            },
                            {
                                "relative_index": 2,
                                "protein": {
                                    "protein_id": "bridge1",
                                    "product": "PF04851 protein",
                                    "pfam": "PF04851",
                                },
                                "clusters": {"30": "bridge30"},
                            },
                        ],
                    },
                }
            ],
            "sequence_evidence": {
                "protein": {"available": True, "protein_id": "neighbor1", "sequence": "MKT"},
                "dna": {"available": True, "protein_id": "neighbor1", "sequence": "ATGAAAACC"},
            },
            "candidate_cohort": [
                {"cluster_30": "nag", "presence_contexts": 12, "protein_length": 1510},
                {"cluster_30": "nag", "presence_contexts": 10, "protein_length": 1490},
                {"cluster_30": "other", "presence_contexts": 2, "protein_length": 1110},
            ],
        },
    }


def test_runtime_records_literature_failure_without_fabricating_motif_logic() -> None:
    provider = ScriptedLLMProvider(
        [
            {
                "main_question": "What is the candidate's system role?",
                "current_program": "literature_regrounding",
                "steps": [
                    {
                        "step_id": "S1",
                        "program_type": "literature_regrounding",
                        "goal": "Check whether the seed and candidate family have reliable literature priors.",
                        "why_now": "The current notebook still lacks literature grounding.",
                        "inputs_required": ["seed_summary", "candidate_neighbor_summary"],
                        "expected_artifacts": ["literature_records"],
                        "branch_conditions": ["If literature fails, defer mechanism and do not create new motif criteria."],
                        "stop_conditions": ["Literature records exist or the bridge is marked failed."],
                        "focus_terms": ["Cas9", "CRISPR"],
                    }
                ],
            },
            {
                "status": "weak",
                "rationale": "Literature grounding failed, so only a conservative candidate-level role claim is retained.",
                "supported_claim": {
                    "label": "unresolved CRISPR-proximal candidate protein",
                    "evidence_refs": [],
                },
                "notebook_summary": ["Literature bridge failed; mechanistic escalation was deferred."],
                "agenda_summary": ["literature_regrounding"],
                "next_program_recommendations": ["semantic_bridge_resolution if a concrete domain clue appears"],
                "evidence_refs": [],
            },
        ]
    )
    executor = EvidenceToolExecutor(literature_client=FailingLiteratureClient())

    result = run_research_runtime(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        runtime_inputs=_runtime_inputs(),
        provider=provider,
        tool_executor=executor,
        max_rounds=1,
    )

    assert result.reasoning["status"] == "weak"
    assert result.ledger["notebook"]["failed_bridges"]
    assert "literature backend unavailable" in result.ledger["notebook"]["failed_bridges"][0]["reason"]
    assert all(run["tool"] != "check_candidate_motifs" for run in result.ledger["tool_runs"])


def test_runtime_executes_semantic_bridge_resolution_before_system_rejection() -> None:
    provider = ScriptedLLMProvider(
        [
            {
                "main_question": "Is the PF04851 neighbor relevant to the seed-linked system hypothesis?",
                "current_program": "semantic_bridge_resolution",
                "steps": [
                    {
                        "step_id": "S1",
                        "program_type": "semantic_bridge_resolution",
                        "goal": "Resolve the meaning of PF04851 before rejecting the system hypothesis.",
                        "why_now": "A concrete accession clue is present in the local context.",
                        "inputs_required": ["occurrence_bundle", "seed_summary"],
                        "expected_artifacts": ["semantic_bridge_summary"],
                        "branch_conditions": ["If PF04851 resolves to a relevant family, revisit the system hypothesis."],
                        "stop_conditions": ["Semantic bridge status is resolved or unresolved."],
                        "focus_terms": ["PF04851"],
                    }
                ],
            },
            {
                "status": "weak",
                "rationale": "The system hypothesis is not falsified before PF04851 is semantically resolved.",
                "supported_claim": {
                    "label": "DNA methyltransferase candidate with unresolved defense-associated neighbor",
                    "evidence_refs": ["TOOL:resolve_semantic_bridge:1"],
                },
                "notebook_summary": ["PF04851 was treated as a semantic bridge before any rejection step."],
                "agenda_summary": ["semantic_bridge_resolution"],
                "next_program_recommendations": ["local_context_discrimination"],
                "evidence_refs": ["TOOL:resolve_semantic_bridge:1"],
            },
        ]
    )
    executor = EvidenceToolExecutor()
    enricher = AccessionEnricher(
        fetchers={
            "Pfam": lambda accession: {
                "source": "Pfam",
                "accession": accession,
                "family_terms": ["Restriction endonuclease-associated family"],
                "raw_label": "restriction endonuclease-associated family",
            }
        }
    )

    result = run_research_runtime(
        candidate_index=1,
        candidate_slug="q1-neighbor30",
        runtime_inputs=_runtime_inputs(),
        provider=provider,
        tool_executor=executor,
        max_rounds=1,
        accession_enricher=enricher,
    )

    assert result.reasoning["supported_claim"]["label"].startswith("DNA methyltransferase candidate")
    assert result.ledger["tool_runs"][0]["tool"] == "resolve_semantic_bridge"
    assert result.ledger["tool_runs"][0]["summary"]["resolved_family_terms"] == [
        "Restriction endonuclease-associated family"
    ]
