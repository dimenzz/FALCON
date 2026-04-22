from __future__ import annotations

from falcon.reporting.markdown import render_agent_report


def test_render_agent_report_uses_supported_claim_notebook_and_next_program_sections() -> None:
    report = render_agent_report(
        {
            "candidate": {
                "query_id": "spCas9",
                "cluster_30": "neighbor30",
                "presence_contexts": 4,
                "query_contexts": 5,
                "fold_enrichment": 12.0,
                "q_value": 0.001,
            },
            "reasoning": {
                "status": "supported_role",
                "rationale": "Family naming and context support a Type II-A adaptation accessory role.",
                "supported_claim": {
                    "label": "Csn2-family accessory protein in a Type II-A adaptation locus",
                    "evidence_refs": ["AUDIT:1"],
                },
                "notebook_summary": [
                    "Stable adaptation-side placement remains the main working interpretation.",
                ],
                "agenda_summary": [
                    "identity_adjudication",
                    "local_context_discrimination",
                ],
                "next_program_recommendations": [
                    "Inspect local sequence architecture for repeat structures near the locus.",
                    "Check occurrence-level loci for stable adaptation-side placement.",
                ],
                "evidence_refs": ["AUDIT:1"],
            },
            "seed_summary": {
                "query_prior": {
                    "function_description": "SpCas9 seed protein",
                },
                "target_consensus_annotation": {
                    "product": "CRISPR-associated endonuclease Cas9",
                    "gene_name": "cas9",
                },
            },
            "sequence_evidence": {
                "protein": {"available": True},
                "dna": {"available": True},
            },
            "examples": [],
            "falsification_checklist": [],
            "uncertainties": [],
            "ledger": {
                "notebook": {
                    "active_question": "What is the candidate's system role?",
                    "failed_bridges": [],
                    "escalation_signals": [],
                    "recent_outcomes": [
                        {"step_id": "S1", "program_type": "identity_adjudication", "status": "ok"},
                    ],
                },
                "agendas": [
                    {
                        "main_question": "What is the candidate's system role?",
                        "current_program": "identity_adjudication",
                        "steps": [
                            {"step_id": "S1", "program_type": "identity_adjudication", "goal": "Summarize annotations"}
                        ],
                    }
                ],
                "audited_claims": [
                    {"step_id": "S1", "program_type": "identity_adjudication", "verdict": "support", "status": "ok"}
                ],
                "tool_runs": [
                    {"tool": "summarize_annotations", "status": "ok"},
                ],
            },
        }
    )

    assert "## Supported Claim" in report
    assert "Csn2-family accessory protein in a Type II-A adaptation locus" in report
    assert "## Research Notebook" in report
    assert "Stable adaptation-side placement remains the main working interpretation." in report
    assert "## Research Agenda" in report
    assert "identity_adjudication" in report
    assert "## Next Program Recommendation" in report
    assert "Inspect local sequence architecture for repeat structures near the locus." in report
