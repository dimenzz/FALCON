from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import DynamicToolReview


def review(runner: RoleRunner, payload: dict[str, Any]) -> DynamicToolReview:
    return runner.call(
        trace_role="dynamic_tool_reviewer",
        prompt_role="dynamic_tool_reviewer",
        schema=DynamicToolReview,
        payload=payload,
    )
