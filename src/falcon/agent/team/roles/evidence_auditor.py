from __future__ import annotations

from typing import Any

from falcon.agent.team.roles.base import RoleRunner
from falcon.agent.team.schemas import AuditReport


def audit(runner: RoleRunner, payload: dict[str, Any]) -> AuditReport:
    return runner.call(
        trace_role="evidence_auditor",
        prompt_role="evidence_auditor",
        schema=AuditReport,
        payload=payload,
    )
