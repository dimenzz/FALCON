from __future__ import annotations

from falcon.tools.agent_registry import (
    AgentToolRunner,
    EvidenceToolExecutor,
    build_candidate_mmseqs_runner,
    build_interproscan_runner,
)

InterProScanRunner = AgentToolRunner

__all__ = [
    "AgentToolRunner",
    "EvidenceToolExecutor",
    "InterProScanRunner",
    "build_candidate_mmseqs_runner",
    "build_interproscan_runner",
]
