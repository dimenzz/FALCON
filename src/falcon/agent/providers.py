from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
import json
import os


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    raw: dict[str, Any] | None = None


class LLMProvider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]], metadata: dict[str, Any]) -> LLMResponse:
        ...


class ScriptedLLMProvider:
    name = "scripted"

    def __init__(self, responses: list[dict[str, Any] | str] | None = None) -> None:
        self._responses = responses or [
            {
                "main_question": "What is the candidate's conservative system role?",
                "current_program": "identity_adjudication",
                "steps": [
                    {
                        "step_id": "S1",
                        "program_type": "identity_adjudication",
                        "goal": "Summarize current annotations before any mechanistic escalation.",
                        "why_now": "The mock runtime should validate basic reasoning plumbing first.",
                        "inputs_required": ["seed_summary", "candidate_neighbor_summary", "occurrence_bundle"],
                        "expected_artifacts": ["annotation_summary"],
                        "branch_conditions": ["If a concrete bridge clue appears, switch to semantic_bridge_resolution."],
                        "stop_conditions": ["A conservative annotation summary is available."],
                        "focus_terms": [],
                    }
                ],
            },
            {
                "status": "weak",
                "rationale": "Scripted mock mode keeps the supported claim conservative and validates runtime plumbing.",
                "supported_claim": {
                    "label": "conservative candidate-level role assignment",
                    "evidence_refs": [],
                },
                "notebook_summary": ["Mock provider validates the notebook/program-planner runtime."],
                "agenda_summary": ["identity_adjudication"],
                "next_program_recommendations": ["semantic_bridge_resolution if a concrete accession clue appears"],
                "evidence_refs": [],
            },
        ]
        self._index = 0

    def complete(self, messages: list[dict[str, str]], metadata: dict[str, Any]) -> LLMResponse:
        if self._index < len(self._responses):
            response = self._responses[self._index]
        else:
            response = {
                "action": "finalize",
                "status": "incomplete",
                "rationale": "Scripted provider exhausted its response list before a final verdict.",
                "evidence": [],
                "uncertainties": ["The scripted provider did not have another response."],
            }
        self._index += 1
        content = response if isinstance(response, str) else json.dumps(response, sort_keys=True)
        return LLMResponse(content=content, provider=self.name, raw={"script_index": self._index})


class ReplayLLMProvider:
    name = "replay"

    def __init__(self, replay_path: Path | str) -> None:
        self._responses = _load_replay_responses(replay_path)
        self._index = 0

    def complete(self, messages: list[dict[str, str]], metadata: dict[str, Any]) -> LLMResponse:
        if self._index >= len(self._responses):
            raise ValueError("Replay provider exhausted all recorded LLM responses")
        content = self._responses[self._index]
        self._index += 1
        return LLMResponse(content=content, provider=self.name, raw={"replay_index": self._index})


class OpenAIChatProvider:
    name = "openai-chat"

    def __init__(
        self,
        *,
        model_name: str | None,
        api_key_env: str,
        base_url: str | None,
        temperature: float,
        max_tokens: int,
    ) -> None:
        if not model_name:
            raise ValueError("agent.llm.model_name must be set for live LLM mode")
        self.model_name = model_name
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict[str, str]], metadata: dict[str, Any]) -> LLMResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI Python SDK is required for live LLM mode. Install the 'openai' package.") from exc

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ValueError(f"Environment variable {self.api_key_env} must be set for live LLM mode")

        kwargs: dict[str, Any] = {"api_key": api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.choices[0].message.content or ""
        raw = response.model_dump() if hasattr(response, "model_dump") else {"response": str(response)}
        return LLMResponse(content=content, provider=self.name, raw=raw)


def _load_replay_responses(replay_path: Path | str) -> list[str]:
    responses = []
    with Path(replay_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            content = record.get("response_content") or record.get("content")
            if not isinstance(content, str):
                raise ValueError(f"Replay record is missing response_content: {record}")
            responses.append(content)
    if not responses:
        raise ValueError(f"Replay file contains no responses: {replay_path}")
    return responses
