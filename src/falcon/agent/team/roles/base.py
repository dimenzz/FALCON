from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar
import json
import re

from pydantic import BaseModel, ValidationError

from falcon.agent.providers import LLMProvider

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class RoleOutputError(ValueError):
    role: str
    attempts: int
    message: str

    def __str__(self) -> str:
        return f"{self.role} failed schema validation after {self.attempts} attempts: {self.message}"


class RoleRunner:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        role_instructions: dict[str, str],
        candidate_index: int,
        candidate_slug: str,
        schema_retries: int,
        role_calls: list[dict[str, Any]],
        event_logger: Any | None = None,
    ) -> None:
        self.provider = provider
        self.role_instructions = role_instructions
        self.candidate_index = candidate_index
        self.candidate_slug = candidate_slug
        self.schema_retries = max(0, int(schema_retries))
        self.role_calls = role_calls
        self.event_logger = event_logger

    def call(
        self,
        *,
        trace_role: str,
        prompt_role: str,
        schema: type[T],
        payload: dict[str, Any],
    ) -> T:
        messages = [
            {"role": "system", "content": self.role_instructions[prompt_role]},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ]
        last_error = ""
        for attempt in range(1, self.schema_retries + 2):
            self._emit_event("role_started", role=trace_role, attempt=attempt)
            response = self.provider.complete(
                messages,
                metadata={
                    "candidate_index": self.candidate_index,
                    "candidate_slug": self.candidate_slug,
                    "role": trace_role,
                    "attempt": attempt,
                },
            )
            try:
                parsed = _load_json_object(response.content)
                model = schema.model_validate(parsed)
            except (json.JSONDecodeError, ValueError, ValidationError) as exc:
                last_error = str(exc)
                self.role_calls.append(
                    _role_record(
                        candidate_index=self.candidate_index,
                        candidate_slug=self.candidate_slug,
                        role=trace_role,
                        attempt=attempt,
                        messages=messages,
                        response_content=response.content,
                        provider=response.provider,
                        parsed=None,
                        raw_response=response.raw,
                        validation_error=last_error,
                    )
                )
                if attempt <= self.schema_retries:
                    messages = [
                        *messages,
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": (
                                "Your response failed schema validation. "
                                f"Error: {last_error}\n"
                                "Return only valid JSON matching this JSON schema:\n"
                                f"{json.dumps(schema.model_json_schema(), sort_keys=True)}"
                            ),
                        },
                    ]
                    continue
                self._emit_event("role_failed", role=trace_role, attempt=attempt, error=last_error)
                raise RoleOutputError(trace_role, attempt, last_error) from exc

            self.role_calls.append(
                _role_record(
                    candidate_index=self.candidate_index,
                    candidate_slug=self.candidate_slug,
                    role=trace_role,
                    attempt=attempt,
                    messages=messages,
                    response_content=response.content,
                    provider=response.provider,
                    parsed=model.model_dump(mode="json"),
                    raw_response=response.raw,
                    validation_error=None,
                )
            )
            self._emit_event("role_finished", role=trace_role, attempt=attempt)
            return model
        raise RoleOutputError(trace_role, self.schema_retries + 1, last_error)

    def _emit_event(self, event: str, **payload: Any) -> None:
        if self.event_logger is None:
            return
        self.event_logger.emit(
            event,
            candidate_index=self.candidate_index,
            candidate_slug=self.candidate_slug,
            **payload,
        )


def _role_record(
    *,
    candidate_index: int,
    candidate_slug: str,
    role: str,
    attempt: int,
    messages: list[dict[str, str]],
    response_content: str,
    provider: str,
    parsed: dict[str, Any] | None,
    raw_response: dict[str, Any] | None,
    validation_error: str | None,
) -> dict[str, Any]:
    record = {
        "candidate_index": candidate_index,
        "candidate_slug": candidate_slug,
        "role": role,
        "attempt": attempt,
        "provider": provider,
        "messages": [dict(message) for message in messages],
        "response_content": response_content,
        "parsed": parsed,
        "raw_response": raw_response,
    }
    if validation_error:
        record["validation_error"] = validation_error
    return record


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced is not None:
        stripped = fenced.group(1)
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("Team agent response JSON must be an object")
    return payload
