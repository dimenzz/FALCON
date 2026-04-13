from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PromptPackError(ValueError):
    pass


@dataclass(frozen=True)
class PromptPack:
    path: Path
    name: str
    version: str
    system: str
    developer_guidance: str
    allowed_actions: tuple[str, ...]
    tool_policy: str
    output_contract: str
    raw: dict[str, Any]


def load_prompt_pack(path: Path | str) -> PromptPack:
    prompt_path = Path(path)
    payload = yaml.safe_load(prompt_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise PromptPackError(f"Prompt pack must contain a YAML mapping: {prompt_path}")

    required_fields = ("name", "version", "system", "developer_guidance", "action_schema", "tool_policy", "output_contract")
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise PromptPackError(
            f"Prompt pack {prompt_path} is missing required fields: {', '.join(missing_fields)}"
        )

    action_schema = payload["action_schema"]
    if not isinstance(action_schema, dict) or "allowed_actions" not in action_schema:
        raise PromptPackError(f"Prompt pack {prompt_path} is missing action_schema.allowed_actions")

    allowed_actions = action_schema["allowed_actions"]
    if not isinstance(allowed_actions, list) or not allowed_actions:
        raise PromptPackError(f"Prompt pack {prompt_path} must define a non-empty allowed_actions list")
    if not all(isinstance(action, str) and action for action in allowed_actions):
        raise PromptPackError(f"Prompt pack {prompt_path} has invalid allowed action entries")

    return PromptPack(
        path=prompt_path,
        name=str(payload["name"]),
        version=str(payload["version"]),
        system=str(payload["system"]),
        developer_guidance=str(payload["developer_guidance"]),
        allowed_actions=tuple(allowed_actions),
        tool_policy=str(payload["tool_policy"]),
        output_contract=str(payload["output_contract"]),
        raw=payload,
    )
