from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import json
import re


DEFAULT_ALLOWED_ACTIONS: tuple[str, ...] = (
    "propose_hypothesis",
    "request_context_summary",
    "request_sequence_summary",
    "compare_example_annotations",
    "record_contradiction",
    "finalize",
)

FINAL_STATUSES: tuple[str, ...] = (
    "known_associated",
    "novel_candidate",
    "supported",
    "weak",
    "conflicting",
    "insufficient",
    "incomplete",
)


class AgentActionError(ValueError):
    pass


@dataclass(frozen=True)
class AgentAction:
    name: str
    payload: dict[str, Any]


def parse_agent_action(text: str, allowed_actions: Iterable[str] = DEFAULT_ALLOWED_ACTIONS) -> AgentAction:
    return validate_agent_action(_load_json_object(text), allowed_actions=allowed_actions)


def validate_agent_action(
    payload: dict[str, Any],
    allowed_actions: Iterable[str] = DEFAULT_ALLOWED_ACTIONS,
) -> AgentAction:
    if not isinstance(payload, dict):
        raise AgentActionError("Agent action must be a JSON object")

    action = payload.get("action")
    if not isinstance(action, str) or not action:
        raise AgentActionError("Agent action must include a non-empty action field")

    allowed = tuple(allowed_actions)
    if action not in allowed:
        raise AgentActionError(f"Action {action!r} is not allowed. Allowed actions: {', '.join(allowed)}")

    if action == "finalize":
        status = payload.get("status")
        rationale = payload.get("rationale")
        if not isinstance(status, str) or not status:
            raise AgentActionError("finalize action requires a non-empty status")
        if status not in FINAL_STATUSES:
            raise AgentActionError(f"finalize status {status!r} is not supported")
        if not isinstance(rationale, str) or not rationale:
            raise AgentActionError("finalize action requires a non-empty rationale")

    return AgentAction(name=action, payload=payload)


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced is not None:
        stripped = fenced.group(1)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AgentActionError(f"Agent response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentActionError("Agent response JSON must be an object")
    return payload
