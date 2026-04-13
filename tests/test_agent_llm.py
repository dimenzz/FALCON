from pathlib import Path
import json

from falcon.agent.providers import ScriptedLLMProvider
from falcon.agent.reasoning import reason_candidates

from test_agent import create_agent_databases, create_agent_sequences, write_candidate


def write_prompt_pack(path: Path) -> Path:
    path.write_text(
        "name: falsification-loop\n"
        "version: 1\n"
        "system: You are a falsification-first metagenomics agent.\n"
        "developer_guidance: Test hypotheses against real occurrence evidence.\n"
        "action_schema:\n"
        "  allowed_actions:\n"
        "    - propose_hypothesis\n"
        "    - request_context_summary\n"
        "    - request_sequence_summary\n"
        "    - compare_example_annotations\n"
        "    - record_contradiction\n"
        "    - finalize\n"
        "tool_policy: Only use read-only evidence actions.\n"
        "output_contract: Return exactly one JSON action object.\n",
        encoding="utf-8",
    )
    return path


def test_reason_candidates_with_mock_llm_writes_trace_and_report(tmp_path: Path) -> None:
    proteins_db, clusters_db = create_agent_databases(tmp_path)
    protein_manifest, genome_manifest = create_agent_sequences(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    prompt_pack = write_prompt_pack(tmp_path / "prompt.yaml")
    write_candidate(candidates_path)
    provider = ScriptedLLMProvider(
        [
            {"action": "request_context_summary", "reason": "Inspect genomic context before concluding."},
            {"action": "compare_example_annotations", "reason": "Check whether examples contradict novelty."},
            {
                "action": "finalize",
                "status": "novel_candidate",
                "rationale": "Strong co-localization exists, but annotations remain hypothetical.",
                "evidence": ["q_value=0.01", "example neighbor is annotated as hypothetical protein"],
                "uncertainties": ["Needs external domain annotation before functional naming."],
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
        llm_mode="mock",
        prompt_pack=prompt_pack,
        max_iterations=6,
        llm_provider=provider,
    )

    results = [
        json.loads(line)
        for line in (out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    trace = [
        json.loads(line)
        for line in (out_dir / "agent_trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    calls = [
        json.loads(line)
        for line in (out_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert summary["llm_mode"] == "mock"
    assert summary["agent_trace"] == str(out_dir / "agent_trace.jsonl")
    assert results[0]["reasoning"]["status"] == "novel_candidate"
    assert results[0]["llm_trace"]["iterations"] == 3
    assert trace[0]["action"]["action"] == "request_context_summary"
    assert trace[1]["observation"]["annotations"][0]["neighbor_product"] == "hypothetical protein"
    assert calls[0]["provider"] == "scripted"
    assert len(calls[0]["messages"]) == 2
    assert len(calls[1]["messages"]) == 4
    report = Path(results[0]["report_path"]).read_text(encoding="utf-8")
    assert "LLM Agent Loop" in report
    assert "Strong co-localization exists" in report


def test_llm_loop_marks_incomplete_when_max_iterations_are_exhausted(tmp_path: Path) -> None:
    proteins_db, clusters_db = create_agent_databases(tmp_path)
    protein_manifest, genome_manifest = create_agent_sequences(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    prompt_pack = write_prompt_pack(tmp_path / "prompt.yaml")
    write_candidate(candidates_path)
    provider = ScriptedLLMProvider(
        [
            {"action": "request_context_summary", "reason": "Still collecting context."},
            {"action": "request_sequence_summary", "reason": "Would inspect sequence next."},
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
        llm_mode="mock",
        prompt_pack=prompt_pack,
        max_iterations=1,
        llm_provider=provider,
    )

    result = json.loads((out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert summary["status_counts"] == {"incomplete": 1}
    assert result["reasoning"]["status"] == "incomplete"
    assert "maximum LLM iterations" in result["reasoning"]["rationale"]


def test_reason_candidates_can_replay_recorded_llm_calls(tmp_path: Path) -> None:
    proteins_db, clusters_db = create_agent_databases(tmp_path)
    protein_manifest, genome_manifest = create_agent_sequences(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    prompt_pack = write_prompt_pack(tmp_path / "prompt.yaml")
    replay_path = tmp_path / "llm_calls.jsonl"
    write_candidate(candidates_path)
    replay_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "response_content": json.dumps(
                        {"action": "request_context_summary", "reason": "Replay context request."}
                    )
                },
                {
                    "response_content": json.dumps(
                        {
                            "action": "finalize",
                            "status": "known_associated",
                            "rationale": "Replay classified this as a known associated component.",
                            "evidence": ["recorded context request"],
                            "uncertainties": [],
                        }
                    )
                },
            ]
        )
        + "\n",
        encoding="utf-8",
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
        llm_mode="replay",
        prompt_pack=prompt_pack,
        max_iterations=4,
        replay_path=replay_path,
    )

    result = json.loads((out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    calls = [
        json.loads(line)
        for line in (out_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert summary["llm_mode"] == "replay"
    assert result["reasoning"]["status"] == "known_associated"
    assert calls[0]["provider"] == "replay"
