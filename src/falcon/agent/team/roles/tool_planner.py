from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import ToolPlan


def plan(runner: RoleRunner, payload: dict[str, Any]) -> ToolPlan:
    return runner.call(
        trace_role="tool_planner",
        prompt_role="tool_planner",
        schema=ToolPlan,
        payload=payload,
    )
