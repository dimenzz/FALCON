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


def test_default_colocation_filtering_is_exploratory() -> None:
    config = load_config()

    assert config["colocation"]["min_presence_rate"] == 0.01
    assert config["colocation"]["max_candidates"] == 100


def test_default_llm_agent_does_not_guess_live_model() -> None:
    config = load_config()

    assert config["agent"]["workflow"] == "deterministic"
    assert config["agent"]["llm"]["mode"] == "deterministic"
    assert config["agent"]["llm"]["model_name"] is None
    assert config["agent"]["llm"]["prompt_pack"] == "prompts/agent/falsification_loop.yaml"
    assert config["agent"]["team"]["max_rounds"] == 2
    assert config["agent"]["team"]["prompt_dir"] == "prompts/agent/team"
    assert config["agent"]["team"]["schema_retries"] == 2
    assert config["agent"]["team"]["ledger_dir"] == "ledgers"
    assert config["agent"]["tools"]["interproscan"]["policy"] == "on_demand"
    assert config["agent"]["tools"]["mmseqs"]["max_hits"] == 25
    assert config["agent"]["literature"]["sources"] == ["europe_pmc", "pubmed"]
