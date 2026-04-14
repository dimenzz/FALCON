from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import SynthesisResult


def synthesize(runner: RoleRunner, payload: dict[str, Any]) -> SynthesisResult:
    return runner.call(
        trace_role="synthesizer",
        prompt_role="synthesizer",
        schema=SynthesisResult,
        payload=payload,
    )
