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
