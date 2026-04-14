from __future__ import annotations

from copy import deepcopy
from typing import Any


CandidateLedger = dict[str, Any]


def initialize_ledger(
    *,
    candidate_index: int,
    candidate_slug: str,
    evidence: dict[str, Any],
) -> CandidateLedger:
    return {
        "candidate_index": candidate_index,
        "candidate_slug": candidate_slug,
        "candidate": deepcopy(evidence.get("candidate", {})),
        "examples": deepcopy(evidence.get("examples", [])),
        "sequence_evidence": deepcopy(evidence.get("sequence_evidence", {})),
        "deterministic_checks": deepcopy(
            evidence.get("deterministic_checks") or evidence.get("falsification_checklist") or []
        ),
        "literature": {
            "queries": [],
            "records": [],
            "brief": {},
            "failed_queries": [],
        },
        "hypotheses": [],
        "falsification_tests": [],
        "evidence_needs": [],
        "tool_plan": [],
        "tool_observations": [],
        "audit": {"findings": []},
        "revisions": [],
        "contradiction_ledger": [],
        "final": {},
        "uncertainties": deepcopy(evidence.get("uncertainties", [])),
    }


def add_literature_records(ledger: CandidateLedger, records: list[dict[str, Any]]) -> None:
    for record in records:
        payload = dict(record)
        if "evidence_ref" not in payload:
            payload["evidence_ref"] = f"L{len(ledger['literature']['records']) + 1}"
        ledger["literature"]["records"].append(payload)


def add_tool_observations(ledger: CandidateLedger, observations: list[dict[str, Any]]) -> None:
    for observation in observations:
        payload = dict(observation)
        if "evidence_ref" not in payload:
            payload["evidence_ref"] = f"TOOL:{payload.get('tool', 'unknown')}:{len(ledger['tool_observations']) + 1}"
        ledger["tool_observations"].append(payload)


def mark_blocked(
    ledger: CandidateLedger,
    *,
    role: str,
    attempts: int,
    error: str,
) -> None:
    ledger["blocked_step"] = {
        "role": role,
        "attempts": attempts,
        "error": error,
    }
