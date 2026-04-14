from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import LiteratureBrief, LiteratureQueryPlan


def plan_queries(runner: RoleRunner, payload: dict[str, Any]) -> LiteratureQueryPlan:
    return runner.call(
        trace_role="literature_scout_queries",
        prompt_role="literature_scout",
        schema=LiteratureQueryPlan,
        payload=payload,
    )


def write_brief(runner: RoleRunner, payload: dict[str, Any]) -> LiteratureBrief:
    return runner.call(
        trace_role="literature_scout_brief",
        prompt_role="literature_scout",
        schema=LiteratureBrief,
        payload=payload,
    )
