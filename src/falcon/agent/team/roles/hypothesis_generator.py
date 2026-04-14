from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import HypothesisSet


def generate(runner: RoleRunner, payload: dict[str, Any]) -> HypothesisSet:
    return runner.call(
        trace_role="hypothesis_generator",
        prompt_role="hypothesis_generator",
        schema=HypothesisSet,
        payload=payload,
    )
