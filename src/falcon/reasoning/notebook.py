from __future__ import annotations

from typing import Any

from falcon.reasoning.types import SeedSummary


def initialize_notebook(*, seed_summary: SeedSummary, active_question: str) -> dict[str, Any]:
    return {
        "seed_prior": {
            "query_id": seed_summary.query_id,
            "header_description": seed_summary.query_prior.get("header_description"),
            "function_description": seed_summary.query_prior.get("function_description"),
            "confidence": seed_summary.query_prior.get("confidence"),
        },
        "active_question": active_question,
        "anomalies": [],
        "failed_bridges": [],
        "competing_explanations": [],
        "missing_capabilities": [],
        "escalation_signals": [],
        "recent_outcomes": [],
        "notes": [],
    }
