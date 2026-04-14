from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import HypothesisRevision


def revise(runner: RoleRunner, payload: dict[str, Any]) -> HypothesisRevision:
    return runner.call(
        trace_role="hypothesis_reviser",
        prompt_role="hypothesis_reviser",
        schema=HypothesisRevision,
        payload=payload,
    )
