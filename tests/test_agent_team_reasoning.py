from pathlib import Path
import json

from falcon.agent.providers import ScriptedLLMProvider
from falcon.agent.reasoning import reason_candidates
from falcon.literature.search import LiteratureRecord, StaticLiteratureClient

from test_agent import create_agent_databases, create_agent_sequences, write_candidate


def test_reason_candidates_team_workflow_writes_candidate_ledgers_and_reports(tmp_path: Path) -> None:
    proteins_db, clusters_db = create_agent_databases(tmp_path)
    protein_manifest, genome_manifest = create_agent_sequences(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    write_candidate(candidates_path)
    provider = ScriptedLLMProvider(
        [
            {"queries": ["CRISPR proximal hypothetical protein"], "rationale": "Need literature grounding."},
            {
                "summary": "CRISPR accessory claims require direct evidence.",
                "key_findings": ["Co-localization alone is insufficient."],
                "constraints": ["Do not infer function from neighbor annotation."],
                "citation_refs": ["L1"],
            },
            {
                "hypotheses": [
                    {
                        "id": "H1",
                        "claim": "The candidate may be a weak CRISPR-proximal accessory protein.",
                        "mechanism": "Unknown.",
                        "expected_observations": ["direct homology or domain evidence"],
                        "alternative_explanations": ["passenger gene"],
                        "evidence_refs": ["L1"],
                    }
                ]
            },
            {
                "tests": [
                    {
                        "id": "T1",
                        "hypothesis_id": "H1",
                        "question": "Does candidate itself have direct CRISPR-like evidence?",
                        "support_criteria": "MMseqs or InterProScan gives relevant hits.",
                        "weaken_criteria": "Only weak or generic hits.",
                        "falsify_criteria": "Strong non-CRISPR function explains it.",
                        "evidence_needed": "direct candidate evidence",
                        "suggested_tools": ["run_candidate_mmseqs"],
                    }
                ]
            },
            {
                "tool_requests": [
                    {
                        "tool": "run_candidate_mmseqs",
                        "reason": "Check candidate itself.",
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
                        "verdict": "unresolved",
                        "rationale": "MMseqs runner was unavailable in the fixture.",
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
                        "claim": "The candidate remains an unresolved CRISPR-proximal protein.",
                        "status": "unresolved",
                        "rationale": "Direct evidence is missing.",
                    }
                ],
                "rejected_hypotheses": [],
                "contradictions": [],
            },
            {
                "status": "weak",
                "rationale": "The candidate is co-localized but direct evidence remains unresolved.",
                "evidence_refs": ["L1", "T1"],
                "accepted_hypotheses": [],
                "rejected_hypotheses": [],
                "unresolved_hypotheses": ["H1"],
                "uncertainties": ["candidate MMseqs evidence is missing in this fixture"],
            },
        ]
    )

    summary = reason_candidates(
        candidates_path=candidates_path,
        proteins_db=proteins_db,
        clusters_db=clusters_db,
        protein_manifest=protein_manifest,
        genome_manifest=genome_manifest,
        out_dir=out_dir,
        max_candidates=10,
        max_examples=5,
        include_sequences=False,
        flank_bp=3,
        sequence_max_bases=100,
        workflow="team",
        llm_mode="mock",
        max_team_rounds=1,
        llm_provider=provider,
        literature_client=StaticLiteratureClient(
            [
                LiteratureRecord(
                    source="pubmed",
                    title="CRISPR accessory proteins",
                    abstract="Candidate proteins require direct domain support.",
                    pmid="1",
                )
            ]
        ),
    )

    results = [
        json.loads(line)
        for line in (out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ledger_path = out_dir / "ledgers" / "0001-q1-neighbor30.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert summary["workflow"] == "team"
    assert summary["candidate_ledgers"] == str(out_dir / "ledgers")
    assert results[0]["ledger_path"] == str(ledger_path)
    assert results[0]["reasoning"]["status"] == "weak"
    assert ledger["literature"]["records"][0]["pmid"] == "1"
    assert ledger["falsification_tests"][0]["hypothesis_id"] == "H1"
    assert ledger["audit"]["findings"][0]["test_id"] == "T1"
    assert ledger["final"]["unresolved_hypotheses"] == ["H1"]
    report = Path(results[0]["report_path"]).read_text(encoding="utf-8")
    assert "Literature Grounding" in report
    assert "Evidence Graph" in report
    assert "Hypothesis-Specific Falsification Tests" in report
    assert "Contradiction Ledger" in report
