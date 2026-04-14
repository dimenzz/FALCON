from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import EvidenceNeeds


def derive(runner: RoleRunner, payload: dict[str, Any]) -> EvidenceNeeds:
    return runner.call(
        trace_role="evidence_needs",
        prompt_role="evidence_needs",
        schema=EvidenceNeeds,
        payload=payload,
    )
