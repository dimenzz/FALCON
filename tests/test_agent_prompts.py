from pathlib import Path

import pytest

from falcon.agent.prompts import PromptPackError, load_prompt_pack


def test_load_prompt_pack_requires_loop_fields(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.yaml"
    prompt_path.write_text(
        "name: too-small\n"
        "version: 1\n"
        "system: You are a careful scientist.\n",
        encoding="utf-8",
    )

    with pytest.raises(PromptPackError, match="action_schema"):
        load_prompt_pack(prompt_path)


def test_load_prompt_pack_reads_yaml_contract(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.yaml"
    prompt_path.write_text(
        "name: falsification-loop\n"
        "version: 1\n"
        "system: You are a careful scientist.\n"
        "developer_guidance: Prefer falsification over speculation.\n"
        "action_schema:\n"
        "  allowed_actions:\n"
        "    - request_context_summary\n"
        "    - finalize\n"
        "tool_policy: Read-only evidence tools only.\n"
        "output_contract: Return one JSON action object.\n",
        encoding="utf-8",
    )

    prompt_pack = load_prompt_pack(prompt_path)

    assert prompt_pack.name == "falsification-loop"
    assert prompt_pack.allowed_actions == ("request_context_summary", "finalize")
    assert "falsification" in prompt_pack.developer_guidance
