from __future__ import annotations

from falcon.reporting.markdown import render_agent_report


def test_render_agent_report_uses_supported_claim_working_hypotheses_and_next_evidence_plan_sections() -> None:
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
                "working_hypotheses": [
                    {
                        "id": "H1",
                        "mechanistic_label": "spacer-acquisition accessory factor",
                        "status": "active",
                    },
                    {
                        "id": "H2",
                        "mechanistic_label": "non-canonical locus accessory factor",
                        "status": "competing",
                    },
                ],
                "next_evidence_plan": [
                    "Inspect local sequence architecture for repeat structures near the locus.",
                    "Check occurrence-level loci for stable adaptation-side placement.",
                ],
                "evidence_refs": ["AUDIT:1"],
            },
            "sequence_evidence": {
                "protein": {"available": True},
                "dna": {"available": True},
            },
            "examples": [],
            "falsification_checklist": [],
            "uncertainties": [],
        }
    )

    assert "## Supported Claim" in report
    assert "Csn2-family accessory protein in a Type II-A adaptation locus" in report
    assert "## Working Mechanistic Hypotheses" in report
    assert "spacer-acquisition accessory factor" in report
    assert "## Next Evidence Collection Plan" in report
    assert "Inspect local sequence architecture for repeat structures near the locus." in report
