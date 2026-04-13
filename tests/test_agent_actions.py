import pytest

from falcon.agent.actions import AgentActionError, validate_agent_action


def test_validate_agent_action_rejects_unknown_tool() -> None:
    with pytest.raises(AgentActionError, match="not allowed"):
        validate_agent_action({"action": "run_interproscan"})


def test_validate_finalize_action_requires_status_and_rationale() -> None:
    with pytest.raises(AgentActionError, match="status"):
        validate_agent_action({"action": "finalize", "rationale": "Strong context"})

    with pytest.raises(AgentActionError, match="rationale"):
        validate_agent_action({"action": "finalize", "status": "novel_candidate"})


def test_validate_agent_action_accepts_read_only_action() -> None:
    action = validate_agent_action(
        {
            "action": "request_context_summary",
            "hypothesis": "Neighbor may be part of the same defense system.",
            "reason": "Need occurrence-level context before concluding.",
        }
    )

    assert action.name == "request_context_summary"
    assert action.payload["hypothesis"].startswith("Neighbor may be")
