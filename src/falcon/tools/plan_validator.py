from __future__ import annotations

from typing import Any

from falcon.tools.manifest import ToolManifest


class ToolPlanValidator:
    def __init__(self, manifest: ToolManifest) -> None:
        self.manifest = manifest

    def validate(
        self,
        requests: list[dict[str, Any]],
        *,
        evidence_needs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[dict[str, Any]] = []
        validations: list[dict[str, Any]] = []
        needs_by_id: dict[str, dict[str, Any]] = {}
        for need in evidence_needs:
            for key in (need.get("id"), need.get("test_id"), need.get("evidence_need_id")):
                if key:
                    needs_by_id[str(key)] = need
        for request in requests:
            tool_id = str(request.get("tool") or "")
            evidence_need_id = str(request.get("evidence_need_id") or request.get("test_id") or "")
            spec = self.manifest.get(tool_id)
            if spec is None:
                validations.append(_validation(request, status="rejected", reason="tool is not in manifest"))
                continue
            if not spec.enabled:
                validations.append(_validation(request, status="rejected", reason="tool is disabled by manifest"))
                continue
            mismatch_terms = _capability_mismatches(
                request=request,
                evidence_need=needs_by_id.get(evidence_need_id, {}),
                cannot_answer=spec.cannot_answer,
            )
            if mismatch_terms:
                validations.append(
                    _validation(
                        request,
                        status="rejected",
                        reason=f"tool capability mismatch: {'; '.join(mismatch_terms)}",
                    )
                )
                continue
            accepted.append(request)
            validations.append(_validation(request, status="accepted", reason="tool capability matched manifest"))
        return accepted, validations


def _capability_mismatches(
    *,
    request: dict[str, Any],
    evidence_need: dict[str, Any],
    cannot_answer: list[str],
) -> list[str]:
    text = " ".join(
        str(value or "")
        for value in (
            request.get("reason"),
            request.get("capability_match"),
            request.get("expected_observation"),
            evidence_need.get("evidence_needed"),
            evidence_need.get("question"),
        )
    ).lower()
    return [term for term in cannot_answer if term.lower() in text]


def _validation(request: dict[str, Any], *, status: str, reason: str) -> dict[str, Any]:
    payload = {
        "tool": request.get("tool"),
        "evidence_need_id": request.get("evidence_need_id") or request.get("test_id"),
        "status": status,
        "reason": reason,
    }
    return {key: value for key, value in payload.items() if value is not None}
