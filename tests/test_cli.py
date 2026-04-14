from pathlib import Path
import json
import sqlite3

from typer.testing import CliRunner

from falcon.cli import app


runner = CliRunner()


def create_fixture_config(tmp_path: Path) -> Path:
    proteins_db = tmp_path / "proteins.db"
    clusters_db = tmp_path / "clusters.db"
    genome_manifest = tmp_path / "genome_manifest.csv"
    protein_manifest = tmp_path / "protein_manifest.csv"
    mmseqs_root = tmp_path / "mmseqs_db"
    mmseqs = tmp_path / "mmseqs"
    interproscan = tmp_path / "interproscan.sh"

    with sqlite3.connect(proteins_db) as conn:
        conn.execute(
            """
            CREATE TABLE proteins (
                protein_id TEXT PRIMARY KEY,
                contig_id TEXT NOT NULL,
                mag_id TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                strand TEXT NOT NULL,
                length INTEGER NOT NULL,
                product TEXT,
                gene_name TEXT,
                locus_tag TEXT,
                pfam TEXT,
                interpro TEXT,
                kegg TEXT,
                cog_category TEXT,
                cog_id TEXT,
                ec_number TEXT,
                eggnog TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO proteins (
                protein_id, contig_id, mag_id, start, end, strand, length,
                product, gene_name, locus_tag, pfam, interpro, kegg,
                cog_category, cog_id, ec_number, eggnog
            )
            VALUES ('p1', 'contigA', 'magA', 100, 160, '+', 20, 'target', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            """
        )

    with sqlite3.connect(clusters_db) as conn:
        conn.execute(
            """
            CREATE TABLE clusters (
                representative_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                cluster_level TEXT NOT NULL,
                PRIMARY KEY (member_id, cluster_level)
            )
            """
        )

    genome_manifest.write_text("magA,/data/genomes/magA.fna\n", encoding="utf-8")
    protein_manifest.write_text("magA,/data/proteins/magA.faa\n", encoding="utf-8")
    mmseqs_root.mkdir()
    mmseqs.write_text("#!/bin/sh\n", encoding="utf-8")
    interproscan.write_text("#!/bin/sh\n", encoding="utf-8")
    mmseqs.chmod(0o755)
    interproscan.chmod(0o755)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
data:
  proteins_db: {proteins_db}
  clusters_db: {clusters_db}
  genome_manifest: {genome_manifest}
  protein_manifest: {protein_manifest}
  mmseqs_db_root: {mmseqs_root}
tools:
  mmseqs: {mmseqs}
  interproscan: {interproscan}
  interproscan_threads: 3
context:
  upstream: 1
  downstream: 1
  include_clusters: true
homology:
  threads: 4
""",
        encoding="utf-8",
    )
    return config_path


def create_phase2_config(tmp_path: Path) -> Path:
    proteins_db = tmp_path / "phase2_proteins.db"
    clusters_db = tmp_path / "phase2_clusters.db"
    genome_manifest = tmp_path / "genome_manifest.csv"
    protein_manifest = tmp_path / "protein_manifest.csv"
    mmseqs_root = tmp_path / "mmseqs_db"
    mmseqs = tmp_path / "mmseqs"
    interproscan = tmp_path / "interproscan.sh"

    with sqlite3.connect(proteins_db) as conn:
        conn.execute(
            """
            CREATE TABLE proteins (
                protein_id TEXT PRIMARY KEY,
                contig_id TEXT NOT NULL,
                mag_id TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                strand TEXT NOT NULL,
                length INTEGER NOT NULL,
                product TEXT,
                gene_name TEXT,
                locus_tag TEXT,
                pfam TEXT,
                interpro TEXT,
                kegg TEXT,
                cog_category TEXT,
                cog_id TEXT,
                ec_number TEXT,
                eggnog TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO proteins (
                protein_id, contig_id, mag_id, start, end, strand, length,
                product, gene_name, locus_tag, pfam, interpro, kegg,
                cog_category, cog_id, ec_number, eggnog
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("rep90a_left", "contigA", "magA", 10, 50, "+", 13, "left", None, None, None, None, None, None, None, None, None),
                ("rep90a", "contigA", "magA", 100, 180, "+", 26, "target", None, None, None, None, None, None, None, None, None),
                ("rep90a_right", "contigA", "magA", 220, 300, "+", 26, "right", None, None, None, None, None, None, None, None, None),
            ],
        )

    with sqlite3.connect(clusters_db) as conn:
        conn.execute(
            """
            CREATE TABLE clusters (
                representative_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                cluster_level TEXT NOT NULL,
                PRIMARY KEY (member_id, cluster_level)
            )
            """
        )
        conn.execute(
            "INSERT INTO clusters (representative_id, member_id, cluster_level) VALUES ('rep30x', 'rep90a', '30')"
        )

    genome_manifest.write_text("magA,/data/genomes/magA.fna\n", encoding="utf-8")
    protein_manifest.write_text("magA,/data/proteins/magA.faa\n", encoding="utf-8")
    mmseqs_root.mkdir()
    (mmseqs_root / "cluster_90").mkdir()
    (mmseqs_root / "cluster_30").mkdir()
    mmseqs.write_text(
        "#!/bin/sh\n"
        "printf 'noisy mmseqs stdout\\n'\n"
        "printf 'noisy mmseqs stderr\\n' >&2\n"
        "printf 'q1\\trep90a\\t80.0\\t10\\t1.0\\t0.9\\t1e-5\\t50\\t10\\t10\\n' > \"$4\"\n",
        encoding="utf-8",
    )
    interproscan.write_text("#!/bin/sh\n", encoding="utf-8")
    mmseqs.chmod(0o755)
    interproscan.chmod(0o755)

    config_path = tmp_path / "phase2_config.yaml"
    config_path.write_text(
        f"""
data:
  proteins_db: {proteins_db}
  clusters_db: {clusters_db}
  genome_manifest: {genome_manifest}
  protein_manifest: {protein_manifest}
  mmseqs_db_root: {mmseqs_root}
tools:
  mmseqs: {mmseqs}
  interproscan: {interproscan}
context:
  upstream: 1
  downstream: 1
  include_clusters: true
homology:
  threads: 4
runtime:
  runs_dir: {tmp_path / "runs"}
  log_dir: {tmp_path / "logs"}
""",
        encoding="utf-8",
    )
    return config_path


def create_sequence_agent_config(tmp_path: Path) -> Path:
    proteins_db = tmp_path / "seq_agent_proteins.db"
    clusters_db = tmp_path / "seq_agent_clusters.db"
    protein_fasta = tmp_path / "magA.faa"
    genome_fasta = tmp_path / "magA.fna"
    genome_manifest = tmp_path / "genome_manifest.csv"
    protein_manifest = tmp_path / "protein_manifest.csv"
    mmseqs_root = tmp_path / "mmseqs_db"
    mmseqs = tmp_path / "mmseqs"
    interproscan = tmp_path / "interproscan.sh"

    with sqlite3.connect(proteins_db) as conn:
        conn.execute(
            """
            CREATE TABLE proteins (
                protein_id TEXT PRIMARY KEY,
                contig_id TEXT NOT NULL,
                mag_id TEXT NOT NULL,
                start INTEGER NOT NULL,
                end INTEGER NOT NULL,
                strand TEXT NOT NULL,
                length INTEGER NOT NULL,
                product TEXT,
                gene_name TEXT,
                locus_tag TEXT,
                pfam TEXT,
                interpro TEXT,
                kegg TEXT,
                cog_category TEXT,
                cog_id TEXT,
                ec_number TEXT,
                eggnog TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO proteins (
                protein_id, contig_id, mag_id, start, end, strand, length,
                product, gene_name, locus_tag, pfam, interpro, kegg,
                cog_category, cog_id, ec_number, eggnog
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("target1", "contigA", "magA", 2, 5, "+", 1, "target", None, None, None, None, None, None, None, None, None),
                ("neighbor1", "contigA", "magA", 7, 10, "-", 1, "hypothetical protein", None, None, None, None, None, None, None, None, None),
            ],
        )

    with sqlite3.connect(clusters_db) as conn:
        conn.execute(
            """
            CREATE TABLE clusters (
                representative_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                cluster_level TEXT NOT NULL,
                PRIMARY KEY (member_id, cluster_level)
            )
            """
        )
        conn.executemany(
            "INSERT INTO clusters (representative_id, member_id, cluster_level) VALUES (?, ?, ?)",
            [
                ("target30", "target1", "30"),
                ("neighbor30", "neighbor1", "30"),
            ],
        )

    protein_fasta.write_text(">target1\nMMM\n>neighbor1\nMKT\n", encoding="utf-8")
    genome_fasta.write_text(">contigA\nAACCGTTACTCC\n", encoding="utf-8")
    genome_manifest.write_text(f"magA,{genome_fasta}\n", encoding="utf-8")
    protein_manifest.write_text(f"magA,{protein_fasta}\n", encoding="utf-8")
    mmseqs_root.mkdir()
    mmseqs.write_text("#!/bin/sh\n", encoding="utf-8")
    interproscan.write_text("#!/bin/sh\n", encoding="utf-8")
    mmseqs.chmod(0o755)
    interproscan.chmod(0o755)

    config_path = tmp_path / "sequence_agent_config.yaml"
    config_path.write_text(
        f"""
data:
  proteins_db: {proteins_db}
  clusters_db: {clusters_db}
  genome_manifest: {genome_manifest}
  protein_manifest: {protein_manifest}
  mmseqs_db_root: {mmseqs_root}
tools:
  mmseqs: {mmseqs}
  interproscan: {interproscan}
runtime:
  runs_dir: {tmp_path / "runs"}
  log_dir: {tmp_path / "logs"}
sequence:
  max_bases: 100
agent:
  max_candidates: 10
  max_examples: 5
  include_sequences: false
  flank_bp: 1
  llm:
    mode: deterministic
""",
        encoding="utf-8",
    )
    return config_path


def test_config_show_prints_effective_json(tmp_path: Path) -> None:
    config_path = create_fixture_config(tmp_path)

    result = runner.invoke(
        app,
        ["config", "show", "--config", str(config_path), "--upstream", "3"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["context"]["upstream"] == 3


def test_config_show_accepts_cluster_cli_overrides(tmp_path: Path) -> None:
    config_path = create_fixture_config(tmp_path)

    result = runner.invoke(
        app,
        [
            "config",
            "show",
            "--config",
            str(config_path),
            "--search-level",
            "30",
            "--statistics-neighbor-level",
            "30",
            "--expand-30-contexts",
            "--threads",
            "10",
            "--interproscan-threads",
            "6",
            "--include-sequences",
            "--flank-bp",
            "12",
            "--sequence-max-bases",
            "500",
            "--colocation-max-candidates",
            "25",
            "--llm-mode",
            "live",
            "--model-name",
            "falcon-test-model",
            "--base-url",
            "https://llm.example/v1",
            "--api-key-env",
            "FALCON_TEST_KEY",
            "--temperature",
            "0.1",
            "--max-tokens",
            "1234",
            "--prompt-pack",
            str(tmp_path / "prompt.yaml"),
            "--max-iterations",
            "8",
            "--agent-workflow",
            "team",
            "--max-team-rounds",
            "3",
            "--team-prompt-dir",
            str(tmp_path / "team_prompts"),
            "--team-schema-retries",
            "4",
            "--team-ledger-dir",
            "candidate_ledgers",
            "--literature-max-results",
            "7",
            "--agent-mmseqs-max-hits",
            "9",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["clusters"]["search_level"] == 30
    assert payload["clusters"]["statistics_neighbor_level"] == 30
    assert payload["clusters"]["expand_30_contexts"] is True
    assert payload["homology"]["search_level"] == 30
    assert payload["homology"]["threads"] == 10
    assert payload["tools"]["interproscan_threads"] == 6
    assert payload["agent"]["include_sequences"] is True
    assert payload["agent"]["flank_bp"] == 12
    assert payload["sequence"]["max_bases"] == 500
    assert payload["colocation"]["max_candidates"] == 25
    assert payload["agent"]["llm"]["mode"] == "live"
    assert payload["agent"]["llm"]["model_name"] == "falcon-test-model"
    assert payload["agent"]["llm"]["base_url"] == "https://llm.example/v1"
    assert payload["agent"]["llm"]["api_key_env"] == "FALCON_TEST_KEY"
    assert payload["agent"]["llm"]["temperature"] == 0.1
    assert payload["agent"]["llm"]["max_tokens"] == 1234
    assert payload["agent"]["llm"]["prompt_pack"] == str(tmp_path / "prompt.yaml")
    assert payload["agent"]["llm"]["max_iterations"] == 8
    assert payload["agent"]["workflow"] == "team"
    assert payload["agent"]["team"]["max_rounds"] == 3
    assert payload["agent"]["team"]["prompt_dir"] == str(tmp_path / "team_prompts")
    assert payload["agent"]["team"]["schema_retries"] == 4
    assert payload["agent"]["team"]["ledger_dir"] == "candidate_ledgers"
    assert payload["agent"]["literature"]["max_results_per_source"] == 7
    assert payload["agent"]["tools"]["mmseqs"]["max_hits"] == 9


def test_inspect_reports_sqlite_and_manifest_status(tmp_path: Path) -> None:
    config_path = create_fixture_config(tmp_path)

    result = runner.invoke(app, ["inspect", "--config", str(config_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sqlite"]["proteins_db"]["ok"] is True
    assert payload["sqlite"]["clusters_db"]["ok"] is True
    assert payload["manifests"]["genome_manifest"]["ok"] is True
    assert payload["tools"]["interproscan"]["executable"] is True


def test_context_command_outputs_context_json(tmp_path: Path) -> None:
    config_path = create_fixture_config(tmp_path)

    result = runner.invoke(app, ["context", "p1", "--config", str(config_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["target"]["protein_id"] == "p1"
    assert payload["query"]["window_mode"] == "genes"


def test_homology_search_command_writes_run_artifacts(tmp_path: Path) -> None:
    config_path = create_phase2_config(tmp_path)
    query_path = tmp_path / "query.faa"
    metadata_path = tmp_path / "seeds.tsv"
    out_dir = tmp_path / "search_run"
    query_path.write_text(">q1 vague\nMKT\n", encoding="utf-8")
    metadata_path.write_text("query_id\tfunction_description\nq1\tseed nuclease\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "homology",
            "search",
            "--query",
            str(query_path),
            "--seed-metadata",
            str(metadata_path),
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert "noisy mmseqs" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["hits"] == 1
    assert payload["threads"] == 4
    assert payload["tool_trace"]["stdout_log"].endswith(".stdout.log")
    assert "noisy mmseqs stdout" in Path(payload["tool_trace"]["stdout_log"]).read_text(encoding="utf-8")
    assert (out_dir / "raw_hits.tsv").exists()
    assert (out_dir / "hits.jsonl").exists()
    seed = json.loads((out_dir / "seeds.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert seed["function_description"] == "seed nuclease"


def test_cohort_build_command_writes_context_artifacts(tmp_path: Path) -> None:
    config_path = create_phase2_config(tmp_path)
    hits_path = tmp_path / "hits.jsonl"
    out_dir = tmp_path / "cohort"
    hits_path.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "target_id": "rep90a",
                "pident": 80.0,
                "alnlen": 10,
                "qcov": 1.0,
                "tcov": 0.9,
                "evalue": 1e-5,
                "bits": 50.0,
                "qlen": 10,
                "tlen": 10,
                "search_level": 90,
                "rank": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "cohort",
            "build",
            "--hits",
            str(hits_path),
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["context_targets"] == 1
    context = json.loads((out_dir / "cohort_contexts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert context["protein_id"] == "rep90a"
    assert context["context"]["target"]["protein_id"] == "rep90a"


def test_background_build_command_writes_background_artifacts(tmp_path: Path) -> None:
    config_path = create_phase2_config(tmp_path)
    out_dir = tmp_path / "background"

    result = runner.invoke(
        app,
        [
            "background",
            "build",
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["total_90_representatives"] == 1
    assert (out_dir / "background_30_abundance.json").exists()
    assert (out_dir / "background_30_abundance.tsv").exists()


def test_colocation_score_command_writes_candidate_artifacts(tmp_path: Path) -> None:
    background_path = tmp_path / "background.json"
    contexts_path = tmp_path / "cohort_contexts.jsonl"
    out_dir = tmp_path / "score"
    background_path.write_text(
        json.dumps(
            {
                "total_90_representatives": 100,
                "clusters": [
                    {
                        "cluster_30": "neighborA",
                        "count_90_representatives": 1,
                        "background_probability": 0.01,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    records = []
    for index in range(3):
        records.append(
            {
                "protein_id": f"target{index}",
                "representative_30": "self30",
                "supporting_hits": [{"query_id": "q1", "target_id": f"target{index}", "bits": 100.0, "evalue": 1e-10, "rank": 1}],
                "context": {
                    "target": {"protein_id": f"target{index}", "clusters": {"30": "self30"}},
                    "context": [
                        {
                            "protein": {"protein_id": f"neighbor{index}", "product": "neighbor"},
                            "clusters": {"30": "neighborA"},
                            "relative_index": 1,
                            "is_target": False,
                        }
                    ],
                },
            }
        )
    contexts_path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "colocation",
            "score",
            "--cohort-contexts",
            str(contexts_path),
            "--background",
            str(background_path),
            "--out-dir",
            str(out_dir),
            "--max-candidates",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["candidates"] == 1
    assert payload["max_candidates"] == 1
    assert payload["filter_diagnostics"]["combined_before_limit"] == 1
    assert (out_dir / "candidate_neighbors.jsonl").exists()
    assert (out_dir / "candidate_neighbors.tsv").exists()


def test_sequence_commands_return_protein_and_dna_json(tmp_path: Path) -> None:
    config_path = create_sequence_agent_config(tmp_path)

    protein_result = runner.invoke(
        app,
        ["sequence", "protein", "--protein-id", "neighbor1", "--config", str(config_path)],
    )
    dna_result = runner.invoke(
        app,
        [
            "sequence",
            "dna",
            "--protein-id",
            "neighbor1",
            "--flank-bp",
            "1",
            "--config",
            str(config_path),
        ],
    )

    assert protein_result.exit_code == 0
    assert json.loads(protein_result.stdout)["sequence"] == "MKT"
    assert dna_result.exit_code == 0
    dna_payload = json.loads(dna_result.stdout)
    assert dna_payload["orientation"] == "protein"
    assert dna_payload["sequence"] == "GAGTAA"


def test_agent_reason_command_writes_results_and_reports(tmp_path: Path) -> None:
    config_path = create_sequence_agent_config(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    candidates_path.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "cluster_30": "neighbor30",
                "presence_contexts": 3,
                "query_contexts": 4,
                "presence_rate": 0.75,
                "fold_enrichment": 10.0,
                "q_value": 0.02,
                "examples": [
                    {
                        "context_protein_id": "target1",
                        "neighbor_protein": {"protein_id": "neighbor1", "product": "hypothetical protein"},
                        "relative_index": 1,
                        "supporting_hits": [{"query_id": "q1", "target_id": "target1"}],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "agent",
            "reason",
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["candidates_processed"] == 1
    results = [
        json.loads(line)
        for line in (out_dir / "agent_results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert results[0]["reasoning"]["status"] == "supported"
    assert Path(results[0]["report_path"]).exists()


def test_agent_reason_live_mode_requires_explicit_model_name(tmp_path: Path) -> None:
    config_path = create_sequence_agent_config(tmp_path)
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    candidates_path.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "cluster_30": "neighbor30",
                "presence_contexts": 3,
                "query_contexts": 4,
                "presence_rate": 0.75,
                "fold_enrichment": 10.0,
                "q_value": 0.02,
                "examples": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "agent",
            "reason",
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
            "--llm-mode",
            "live",
        ],
    )

    assert result.exit_code == 1
    assert "agent.llm.model_name" in result.stderr


def test_agent_reason_command_runs_mock_llm_loop(tmp_path: Path) -> None:
    config_path = create_sequence_agent_config(tmp_path)
    prompt_pack = tmp_path / "prompt.yaml"
    candidates_path = tmp_path / "candidate_neighbors.jsonl"
    out_dir = tmp_path / "agent"
    prompt_pack.write_text(
        "name: falsification-loop\n"
        "version: 1\n"
        "system: You are a falsification-first agent.\n"
        "developer_guidance: Test before concluding.\n"
        "action_schema:\n"
        "  allowed_actions:\n"
        "    - request_context_summary\n"
        "    - compare_example_annotations\n"
        "    - finalize\n"
        "tool_policy: Read-only evidence actions only.\n"
        "output_contract: Return one JSON action object.\n",
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "cluster_30": "neighbor30",
                "presence_contexts": 3,
                "query_contexts": 4,
                "presence_rate": 0.75,
                "fold_enrichment": 10.0,
                "q_value": 0.02,
                "examples": [
                    {
                        "context_protein_id": "target1",
                        "neighbor_protein": {"protein_id": "neighbor1", "product": "hypothetical protein"},
                        "relative_index": 1,
                        "supporting_hits": [{"query_id": "q1", "target_id": "target1"}],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "agent",
            "reason",
            "--candidates",
            str(candidates_path),
            "--config",
            str(config_path),
            "--out-dir",
            str(out_dir),
            "--llm-mode",
            "mock",
            "--prompt-pack",
            str(prompt_pack),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["llm_mode"] == "mock"
    assert Path(payload["agent_trace"]).exists()
    assert Path(payload["llm_calls"]).exists()
