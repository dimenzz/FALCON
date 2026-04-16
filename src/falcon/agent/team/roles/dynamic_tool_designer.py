from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import DynamicToolDesign


def design(runner: RoleRunner, payload: dict[str, Any]) -> DynamicToolDesign:
    return runner.call(
        trace_role="dynamic_tool_designer",
        prompt_role="dynamic_tool_designer",
        schema=DynamicToolDesign,
        payload=payload,
    )
