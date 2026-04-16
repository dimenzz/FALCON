from __future__ import annotations

from falcon.agent.providers import ScriptedLLMProvider
from falcon.agent.team import run_team_loop
from falcon.tools.agent_registry import EvidenceToolExecutor


class StubAccessionEnricher:
    def enrich_candidate(self, representative_neighbor: dict, *, cache_dir: str | None = None) -> list[dict]:
        return [
            {
                "source": "Pfam",
                "accession": "PF09711",
                "family_terms": ["Csn2"],
                "raw_label": "CRISPR-associated protein Csn2",
            },
            {
                "source": "KEGG",
                "accession": "K19137",
                "family_terms": ["Csn2"],
                "raw_label": "Csn2 family protein",
            },
            {
                "source": "InterPro",
                "accession": "IPR010146",
                "family_terms": ["Csn2"],
                "raw_label": "CRISPR-associated protein Csn2 family",
            },
        ]


def evidence_packet() -> dict:
    return {
        "candidate": {
            "query_id": "spCas9",
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
                    "pfam": "PF09711",
                    "interpro": "IPR010146",
                    "kegg": "K19137",
                    "cog_id": None,
                },
                "neighbor_clusters": {"30": "neighbor30"},
                "relative_index": 1,
                "context": {
                    "context": [
                        {
                            "relative_index": 0,
                            "protein": {"protein_id": "target1", "product": "Cas9", "gene_name": "cas9"},
                            "clusters": {"30": "seed30"},
                        },
                        {
                            "relative_index": 1,
                            "protein": {"protein_id": "neighbor1", "product": "hypothetical protein", "pfam": "PF09711"},
                            "clusters": {"30": "neighbor30"},
                        },
                    ]
                },
            }
        ],
        "sequence_evidence": {
            "protein": {"available": True, "protein_id": "neighbor1", "sequence": "MKT"},
            "dna": {"available": True},
        },
        "deterministic_checks": [{"question": "signal", "status": "pass", "evidence": "q=0.01"}],
        "uncertainties": [],
    }


def scripted_backbone_provider() -> ScriptedLLMProvider:
    return ScriptedLLMProvider(
        [
            {
                "queries": ["Csn2 Type II-A adaptation locus"],
                "rationale": "Ground the selected family term in the observed system context.",
            },
            {
                "summaries": [
                    {
                        "scope": "family prior",
                        "summary": "Csn2 is a Type II-A CRISPR-associated accessory family.",
                        "key_findings": ["Csn2 is commonly discussed with adaptation modules."],
                        "constraints": ["Do not claim a specific biochemical mechanism from family naming alone."],
                        "citation_refs": ["L1"],
                    },
                    {
                        "scope": "system prior",
                        "summary": "Type II-A loci place Csn2 with Cas9-Cas1-Cas2 adaptation architecture.",
                        "key_findings": ["Adaptation-side placement matters for interpretation."],
                        "constraints": [],
                        "citation_refs": ["L1"],
                    },
                    {
                        "scope": "mechanism caution",
                        "summary": "Specific spacer-acquisition mechanisms need direct locus evidence.",
                        "key_findings": [],
                        "constraints": ["Do not overstate mechanism from context alone."],
                        "citation_refs": ["L1"],
                    },
                ]
            },
            {
                "hypotheses": [
                    {
                        "id": "H1",
                        "mechanistic_label": "adaptation-associated accessory factor",
                        "role_level": "main",
                        "why_it_matches": "Csn2 family naming and adaptation-side placement are consistent with a Type II-A accessory role.",
                        "predicted_observations": ["stable adaptation-side placement"],
                        "disconfirming_observations": ["frequent separation from adaptation proteins"],
                        "open_evidence_gaps": ["repeat-structure evidence near the locus"],
                    },
                    {
                        "id": "H2",
                        "mechanistic_label": "non-canonical locus accessory factor",
                        "role_level": "competing",
                        "why_it_matches": "The family could still support a different local accessory role.",
                        "predicted_observations": ["variable neighborhood placement"],
                        "disconfirming_observations": ["stable adaptation-side placement"],
                        "open_evidence_gaps": ["broader context variation"],
                    },
                ]
            },
            {
                "tests": [
                    {
                        "id": "T1",
                        "hypothesis_id": "H1",
                        "question": "Is the candidate consistently supported by candidate-level family-consistent evidence?",
                        "support_criteria": "family-consistent direct evidence is present",
                        "weaken_criteria": "direct evidence is weak or generic",
                        "falsify_criteria": "strong contradictory family evidence appears",
                        "evidence_needed": "candidate family-consistent evidence",
                        "suggested_tools": ["run_candidate_mmseqs"],
                    }
                ]
            },
            {
                "tool_requests": [
                    {
                        "tool": "run_candidate_mmseqs",
                        "reason": "Need direct candidate-level homology evidence.",
                        "evidence_need_id": "T1",
                        "parameters": {"protein_id": "neighbor1", "max_hits": 3},
                    }
                ],
                "skipped_needs": [],
            },
            {
                "audits": [
                    {
                        "test_id": "T1",
                        "hypothesis_id": "H1",
                        "verdict": "support",
                        "rationale": "Direct homology evidence is family-consistent but not mechanistically specific.",
                        "evidence_refs": ["TOOL:run_candidate_mmseqs:1"],
                        "contradictions": [],
                    }
                ]
            },
            {
                "revised_hypotheses": [
                    {
                        "id": "H1",
                        "version": 2,
                        "claim": "Csn2-family accessory role remains the lead interpretation.",
                        "status": "retained",
                        "rationale": "The new evidence supports the family-consistent role without overclaiming mechanism.",
                    }
                ],
                "rejected_hypotheses": [],
                "contradictions": [],
            },
            {
                "status": "supported_role",
                "rationale": "Family naming and direct candidate evidence support a Type II-A accessory role.",
                "evidence_refs": ["T1", "TOOL:run_candidate_mmseqs:1"],
                "supported_claim": {
                    "label": "Csn2-family accessory protein in a Type II-A adaptation locus",
                    "evidence_refs": ["T1", "TOOL:run_candidate_mmseqs:1"],
                },
                "working_hypotheses": [
                    {
                        "id": "H1",
                        "mechanistic_label": "adaptation-associated accessory factor",
                        "status": "active",
                    },
                    {
                        "id": "H2",
                        "mechanistic_label": "non-canonical locus accessory factor",
                        "status": "competing",
                    },
                ],
                "next_evidence_plan": [
                    "Inspect local sequence architecture for repeat structures.",
                ],
                "accepted_hypotheses": ["H1"],
                "rejected_hypotheses": [],
                "unresolved_hypotheses": ["H2"],
                "uncertainties": [],
            },
        ]
    )


def test_team_loop_records_family_selection_scoped_literature_and_tool_summaries() -> None:
    executor = EvidenceToolExecutor(
        mmseqs_runner=lambda request, evidence: {
            "tool": "run_candidate_mmseqs",
            "status": "ok",
            "protein_id": request["parameters"]["protein_id"],
            "evidence_ref": "TOOL:run_candidate_mmseqs:1",
            "hits": [{"target_id": "csn2_rep", "bits": 180.0}],
        }
    )

    result = run_team_loop(
        candidate_index=1,
        candidate_slug="spcas9-neighbor30",
        evidence=evidence_packet(),
        provider=scripted_backbone_provider(),
        tool_executor=executor,
        max_rounds=1,
        accession_enricher=StubAccessionEnricher(),
        accession_cache_dir="/tmp/falcon-accession-cache",
    )

    assert result.ledger["family_naming"]["selection"]["selected_family_term"] == "Csn2"
    assert result.ledger["family_naming"]["selection"]["selected_source"] == "KEGG"
    assert result.ledger["literature"]["scoped_summaries"][0]["scope"] == "family prior"
    assert result.ledger["tool_summaries"][0]["summary_type"] == "candidate_homology"
    assert result.reasoning["supported_claim"]["label"] == "Csn2-family accessory protein in a Type II-A adaptation locus"
