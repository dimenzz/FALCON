from pathlib import Path

from falcon.config import load_config


def test_yaml_overrides_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "context:\n"
        "  upstream: 2\n"
        "data:\n"
        "  proteins_db: /tmp/proteins.sqlite\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["context"]["upstream"] == 2
    assert config["context"]["downstream"] == 5
    assert config["data"]["proteins_db"] == "/tmp/proteins.sqlite"


def test_cli_overrides_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "context:\n"
        "  upstream: 2\n"
        "data:\n"
        "  proteins_db: /tmp/yaml.sqlite\n",
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        cli_overrides={
            "context": {"upstream": 7},
            "data": {"proteins_db": "/tmp/cli.sqlite"},
        },
    )

    assert config["context"]["upstream"] == 7
    assert config["data"]["proteins_db"] == "/tmp/cli.sqlite"


def test_config_relative_paths_resolve_against_project_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    config_dir = repo / "configs"
    config_dir.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    config_path = config_dir / "default.yaml"
    config_path.write_text(
        """
data:
  genome_manifest: data/data_manifests/genome_manifest.csv
  protein_manifest: data/data_manifests/protein_manifest.csv
agent:
  query_catalog: runs/example-search/seeds.jsonl
  program_planner:
    prompt_dir: prompts/agent/reasoning
    schema_retries: 3
  tools:
    manifest: configs/tool_manifest.yaml
  reporting:
    ledger_dir: ledgers
runtime:
  runs_dir: runs
  log_dir: logs
  event_log: agent_events.jsonl
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["data"]["genome_manifest"] == str(repo / "data/data_manifests/genome_manifest.csv")
    assert config["data"]["protein_manifest"] == str(repo / "data/data_manifests/protein_manifest.csv")
    assert config["agent"]["query_catalog"] == str(repo / "runs/example-search/seeds.jsonl")
    assert config["agent"]["program_planner"]["prompt_dir"] == str(repo / "prompts/agent/reasoning")
    assert config["agent"]["tools"]["manifest"] == str(repo / "configs/tool_manifest.yaml")
    assert config["runtime"]["runs_dir"] == str(repo / "runs")
    assert config["runtime"]["log_dir"] == str(repo / "logs")
    assert config["agent"]["reporting"]["ledger_dir"] == "ledgers"
    assert config["runtime"]["event_log"] == "agent_events.jsonl"


def test_cli_relative_path_overrides_remain_cwd_relative(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
data:
  genome_manifest: yaml_manifest.csv
""",
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        cli_overrides={"data": {"genome_manifest": "cli_manifest.csv"}},
    )

    assert config["data"]["genome_manifest"] == "cli_manifest.csv"


def test_default_colocation_filtering_is_exploratory() -> None:
    config = load_config()

    assert config["colocation"]["min_presence_rate"] == 0.01
    assert config["colocation"]["max_candidates"] == 100


def test_default_llm_agent_does_not_guess_live_model() -> None:
    config = load_config()

    assert config["agent"]["query_catalog"] is None
    assert config["agent"]["llm"]["mode"] == "mock"
    assert config["agent"]["llm"]["model_name"] is None
    assert config["agent"]["program_planner"]["max_rounds"] == 2
    assert config["agent"]["program_planner"]["prompt_dir"] == "prompts/agent/reasoning"
    assert config["agent"]["program_planner"]["schema_retries"] == 2
    assert config["agent"]["reporting"]["ledger_dir"] == "ledgers"
    assert config["agent"]["tools"]["interproscan"]["policy"] == "on_demand"
    assert config["agent"]["tools"]["manifest"] == "configs/tool_manifest.yaml"
    assert config["agent"]["tools"]["mmseqs"]["max_hits"] == 25
    assert config["agent"]["literature"]["sources"] == ["europe_pmc", "pubmed"]


def test_legacy_agent_keys_fail_with_migration_hint(tmp_path: Path) -> None:
    config_path = tmp_path / "legacy.yaml"
    config_path.write_text(
        """
agent:
  workflow: team
  team:
    prompt_dir: prompts/agent/team
  llm:
    prompt_pack: prompts/agent/falsification_loop.yaml
""",
        encoding="utf-8",
    )

    try:
        load_config(config_path)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("legacy agent keys should fail")

    assert "removed agent configuration keys" in message
    assert "agent.workflow" in message
    assert "agent.team" in message
