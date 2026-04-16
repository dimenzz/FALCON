from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import re

from falcon.literature.search import LiteratureClient, StaticLiteratureClient
from falcon.tools.local_architecture import probe_local_sequence_architecture
from falcon.tools.manifest import ToolManifest, default_tool_manifest


AgentToolRunner = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class EvidenceToolExecutor:
    allowlisted_tools = {
        "search_literature",
        "inspect_context",
        "summarize_annotations",
        "query_context_features",
        "check_candidate_motifs",
        "local_sequence_architecture_probe",
        "run_interproscan",
        "run_candidate_mmseqs",
    }

    def __init__(
        self,
        *,
        literature_client: LiteratureClient | None = None,
        interproscan_runner: AgentToolRunner | None = None,
        mmseqs_runner: AgentToolRunner | None = None,
        tool_manifest: ToolManifest | None = None,
        max_expensive_tools_per_candidate: int | None = None,
        event_logger: Any | None = None,
        literature_max_results: int = 5,
        interproscan_policy: str = "on_demand",
    ) -> None:
        self.literature_client = literature_client or StaticLiteratureClient([])
        self.interproscan_runner = interproscan_runner
        self.mmseqs_runner = mmseqs_runner
        self.tool_manifest = tool_manifest or default_tool_manifest()
        self.max_expensive_tools_per_candidate = max_expensive_tools_per_candidate
        self.event_logger = event_logger
        self.literature_max_results = int(literature_max_results)
        self.interproscan_policy = interproscan_policy

    def execute_requests(
        self,
        requests: list[dict[str, Any]],
        evidence: dict[str, Any],
        *,
        event_context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        results = []
        literature_records = []
        expensive_tools_used = 0
        for request in requests:
            tool = request.get("tool")
            spec = self.tool_manifest.get(str(tool)) if tool else None
            if spec is None:
                result = {"tool": tool, "status": "rejected", "reason": "tool is not in manifest"}
            elif not spec.enabled:
                result = {"tool": tool, "status": "skipped", "reason": "tool is disabled by manifest"}
            elif (
                spec.cost_tier == "expensive"
                and self.max_expensive_tools_per_candidate is not None
                and expensive_tools_used >= int(self.max_expensive_tools_per_candidate)
            ):
                result = {"tool": tool, "status": "deferred", "reason": "expensive tool budget exhausted"}
            else:
                if spec.cost_tier == "expensive":
                    expensive_tools_used += 1
                self._emit_event("tool_started", tool=str(tool), event_context=event_context)
                if tool == "search_literature":
                    result = self._search_literature(request)
                    literature_records.extend(result.get("records", []))
                elif tool == "inspect_context":
                    result = self._inspect_context(request, evidence)
                elif tool == "summarize_annotations":
                    result = self._summarize_annotations(request, evidence)
                elif tool == "query_context_features":
                    result = self._query_context_features(request, evidence)
                elif tool == "check_candidate_motifs":
                    result = self._check_candidate_motifs(request, evidence)
                elif tool == "local_sequence_architecture_probe":
                    result = self._local_sequence_architecture_probe(request, evidence)
                elif tool == "run_interproscan":
                    result = self._run_interproscan(request, evidence)
                elif tool == "run_candidate_mmseqs":
                    result = self._run_candidate_mmseqs(request, evidence)
                else:
                    result = {"tool": tool, "status": "rejected", "reason": "tool runner is not implemented"}
                self._emit_event(
                    "tool_finished",
                    tool=str(tool),
                    event_context=event_context,
                    status=str(result.get("status")),
                )
            results.append(result)
        return results, literature_records

    def _emit_event(self, event: str, *, tool: str, event_context: dict[str, Any] | None, **payload: Any) -> None:
        if self.event_logger is None:
            return
        self.event_logger.emit(event, **(event_context or {}), tool=tool, **payload)

    def _search_literature(self, request: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        query = str(parameters.get("query") or request.get("query") or "").strip()
        if not query:
            return {"tool": "search_literature", "status": "skipped", "reason": "empty query", "records": []}
        try:
            records = self.literature_client.search(query, int(parameters.get("max_results", self.literature_max_results)))
        except Exception as exc:
            return {
                "tool": "search_literature",
                "status": "error",
                "query": query,
                "error_type": type(exc).__name__,
                "reason": str(exc),
                "records": [],
            }
        return {
            "tool": "search_literature",
            "status": "ok",
            "query": query,
            "records": [record.to_dict() for record in records],
        }

    def _inspect_context(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        protein_id = parameters.get("protein_id")
        matches = [
            example
            for example in evidence.get("examples", [])
            if not protein_id or example.get("neighbor_protein_id") == protein_id or example.get("context_protein_id") == protein_id
        ]
        return {
            "tool": "inspect_context",
            "status": "ok",
            "protein_id": protein_id,
            "examples": matches,
        }

    def _summarize_annotations(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        annotations = []
        for example in evidence.get("examples", []):
            neighbor = example.get("neighbor_protein") or {}
            annotations.append(
                {
                    "protein_id": example.get("neighbor_protein_id") or neighbor.get("protein_id"),
                    "product": neighbor.get("product"),
                    "pfam": neighbor.get("pfam"),
                    "interpro": neighbor.get("interpro"),
                    "relative_index": example.get("relative_index"),
                }
            )
        return {"tool": "summarize_annotations", "status": "ok", "annotations": annotations}

    def _query_context_features(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        patterns = _string_list(parameters.get("patterns") or parameters.get("pattern") or parameters.get("query"))
        if not patterns:
            return {"tool": "query_context_features", "status": "skipped", "reason": "no query patterns were provided"}
        fields = set(_string_list(parameters.get("fields"))) or {
            "product",
            "gene_name",
            "pfam",
            "interpro",
            "kegg",
            "cog_id",
            "cog_category",
            "protein_id",
        }
        matches = []
        for example_index, example in enumerate(evidence.get("examples", []), start=1):
            example_matches = []
            for item in (example.get("context") or {}).get("context", []):
                protein = item.get("protein") or {}
                clusters = item.get("clusters") or {}
                haystack = " ".join(
                    str(value or "")
                    for key, value in protein.items()
                    if key in fields
                )
                haystack = f"{haystack} {' '.join(str(value) for value in clusters.values())}".lower()
                matched_patterns = [pattern for pattern in patterns if str(pattern).lower() in haystack]
                if not matched_patterns:
                    continue
                example_matches.append(
                    {
                        "protein_id": protein.get("protein_id"),
                        "relative_index": item.get("relative_index"),
                        "product": protein.get("product"),
                        "gene_name": protein.get("gene_name"),
                        "pfam": protein.get("pfam"),
                        "interpro": protein.get("interpro"),
                        "clusters": clusters,
                        "matched_patterns": matched_patterns,
                    }
                )
            if example_matches:
                matches.append(
                    {
                        "example_index": example_index,
                        "context_protein_id": example.get("context_protein_id"),
                        "neighbor_protein_id": example.get("neighbor_protein_id"),
                        "matches": example_matches,
                    }
                )
        return {
            "tool": "query_context_features",
            "status": "ok",
            "patterns": patterns,
            "matches": matches,
            "summary": {
                "contexts_examined": len(evidence.get("examples", [])),
                "contexts_with_matches": len(matches),
                "total_matches": sum(len(match["matches"]) for match in matches),
            },
        }

    def _check_candidate_motifs(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        protein = evidence.get("sequence_evidence", {}).get("protein", {})
        sequence = str(protein.get("sequence") or "")
        if not sequence:
            return {
                "tool": "check_candidate_motifs",
                "status": "skipped",
                "reason": "protein sequence is unavailable in evidence packet",
            }
        parameters = _parameters(request)
        motifs = parameters.get("motifs") or []
        if isinstance(motifs, dict):
            motifs = [motifs]
        if isinstance(motifs, str):
            motifs = [{"id": motifs, "pattern": motifs}]
        results = []
        for index, motif in enumerate(motifs, start=1):
            if not isinstance(motif, dict):
                motif = {"id": f"motif_{index}", "pattern": str(motif)}
            pattern = str(motif.get("pattern") or motif.get("regex") or "")
            if not pattern:
                results.append({"id": motif.get("id") or f"motif_{index}", "pattern": pattern, "matches": []})
                continue
            try:
                matches = [
                    {"start": match.start() + 1, "end": match.end(), "match": match.group(0)}
                    for match in re.finditer(pattern, sequence)
                ]
            except re.error as exc:
                return {
                    "tool": "check_candidate_motifs",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                }
            results.append({"id": motif.get("id") or f"motif_{index}", "pattern": pattern, "matches": matches})
        return {
            "tool": "check_candidate_motifs",
            "status": "ok",
            "protein_id": protein.get("protein_id"),
            "sequence_length": len(sequence),
            "motifs": results,
        }

    def _run_interproscan(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        force = bool(parameters.get("force") or request.get("force"))
        if self.interproscan_policy == "on_demand" and _has_existing_domain_annotations(evidence) and not force:
            return {
                "tool": "run_interproscan",
                "status": "skipped",
                "reason": "existing annotations are sufficient for on-demand policy",
            }
        protein = evidence.get("sequence_evidence", {}).get("protein", {})
        if not protein.get("sequence"):
            return {
                "tool": "run_interproscan",
                "status": "skipped",
                "reason": "protein sequence is unavailable in evidence packet",
            }
        if self.interproscan_runner is None:
            return {
                "tool": "run_interproscan",
                "status": "skipped",
                "reason": "interproscan runner is not configured",
            }
        try:
            return self.interproscan_runner(request, evidence)
        except Exception as exc:
            return {
                "tool": "run_interproscan",
                "status": "error",
                "protein_id": parameters.get("protein_id") or protein.get("protein_id"),
                "error_type": type(exc).__name__,
                "reason": str(exc),
            }

    def _run_candidate_mmseqs(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        protein = evidence.get("sequence_evidence", {}).get("protein", {})
        if not protein.get("sequence"):
            return {
                "tool": "run_candidate_mmseqs",
                "status": "skipped",
                "reason": "protein sequence is unavailable in evidence packet",
            }
        if self.mmseqs_runner is None:
            return {
                "tool": "run_candidate_mmseqs",
                "status": "skipped",
                "reason": "candidate MMseqs runner is not configured",
            }
        try:
            return self.mmseqs_runner(request, evidence)
        except Exception as exc:
            return {
                "tool": "run_candidate_mmseqs",
                "status": "error",
                "protein_id": _parameters(request).get("protein_id") or protein.get("protein_id"),
                "error_type": type(exc).__name__,
                "reason": str(exc),
            }

    def _local_sequence_architecture_probe(self, request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        dna = evidence.get("sequence_evidence", {}).get("dna", {})
        sequence = str(dna.get("sequence") or "")
        if not sequence:
            return {
                "tool": "local_sequence_architecture_probe",
                "status": "skipped",
                "reason": "dna sequence is unavailable in evidence packet",
            }
        parameters = _parameters(request)
        probe = probe_local_sequence_architecture(
            sequence=sequence,
            min_repeat_unit_length=int(parameters.get("min_repeat_unit_length", 4)),
            max_repeat_unit_length=int(parameters.get("max_repeat_unit_length", 12)),
            min_copy_count=int(parameters.get("min_copy_count", 2)),
        )
        return {
            "tool": "local_sequence_architecture_probe",
            "status": "ok",
            "sequence_length": len(sequence),
            "features": probe["features"],
            "summary": probe["summary"],
        }


def build_interproscan_runner(
    *,
    interproscan_path: Path | str | None,
    threads: int,
    output_dir: Path | str,
    log_dir: Path | str,
    event_logger: Any | None = None,
    heartbeat_seconds: float | None = None,
) -> AgentToolRunner | None:
    if interproscan_path is None:
        return None

    from falcon.tools.interproscan import build_interproscan_command, parse_interproscan_tsv
    from falcon.tools.runner import run_external_command

    def _runner(request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        protein = evidence.get("sequence_evidence", {}).get("protein", {})
        protein_id = str(parameters.get("protein_id") or protein.get("protein_id") or "candidate")
        safe_id = _safe_id(protein_id)
        tool_dir = Path(output_dir) / "interproscan"
        tool_dir.mkdir(parents=True, exist_ok=True)
        fasta_path = tool_dir / f"{safe_id}.faa"
        fasta_path.write_text(f">{protein_id}\n{protein['sequence']}\n", encoding="utf-8")
        command = build_interproscan_command(
            interproscan_path=interproscan_path,
            input_fasta=fasta_path,
            output_dir=tool_dir,
            threads=threads,
        )
        trace = run_external_command(
            command=command,
            log_dir=log_dir,
            label=f"interproscan-{safe_id}",
            event_logger=event_logger,
            heartbeat_seconds=heartbeat_seconds,
            event_context={"tool": "run_interproscan", "protein_id": protein_id},
        )
        return {
            "tool": "run_interproscan",
            "status": "ok",
            "protein_id": protein_id,
            "input_fasta": str(fasta_path),
            "trace": trace,
            "domains": _parse_interproscan_domains(tool_dir, parse_interproscan_tsv=parse_interproscan_tsv),
        }

    return _runner


def build_candidate_mmseqs_runner(
    *,
    mmseqs_path: Path | str | None,
    mmseqs_db_root: Path | str | None,
    output_dir: Path | str,
    log_dir: Path | str,
    search_level: int,
    sensitivity: float,
    evalue: float,
    max_hits: int,
    threads: int,
    event_logger: Any | None = None,
    heartbeat_seconds: float | None = None,
) -> AgentToolRunner | None:
    if mmseqs_path is None or mmseqs_db_root is None:
        return None

    from falcon.homology.search import parse_hits_tsv, run_mmseqs_search, target_db_for_level

    def _runner(request: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        parameters = _parameters(request)
        protein = evidence.get("sequence_evidence", {}).get("protein", {})
        protein_id = str(parameters.get("protein_id") or protein.get("protein_id") or "candidate")
        level = int(parameters.get("search_level", search_level))
        limit = int(parameters.get("max_hits", max_hits))
        safe_id = _safe_id(protein_id)
        tool_dir = Path(output_dir) / "candidate_mmseqs"
        tool_dir.mkdir(parents=True, exist_ok=True)
        query_fasta = tool_dir / f"{safe_id}.faa"
        raw_hits = tool_dir / f"{safe_id}.hits.tsv"
        tmp_dir = tool_dir / f"{safe_id}.tmp"
        query_fasta.write_text(f">{protein_id}\n{protein['sequence']}\n", encoding="utf-8")
        trace = run_mmseqs_search(
            mmseqs_path=mmseqs_path,
            query_fasta=query_fasta,
            target_db=target_db_for_level(mmseqs_db_root, level),
            output_tsv=raw_hits,
            tmp_dir=tmp_dir,
            sensitivity=sensitivity,
            evalue=evalue,
            max_seqs=limit,
            threads=threads,
            log_dir=log_dir,
            event_logger=event_logger,
            heartbeat_seconds=heartbeat_seconds,
            event_context={"tool": "run_candidate_mmseqs", "protein_id": protein_id},
        )
        hits = [hit.to_dict() for hit in parse_hits_tsv(raw_hits, search_level=level)[:limit]]
        return {
            "tool": "run_candidate_mmseqs",
            "status": "ok",
            "protein_id": protein_id,
            "query_fasta": str(query_fasta),
            "raw_hits": str(raw_hits),
            "hits": hits,
            "trace": trace,
        }

    return _runner


def _parameters(request: dict[str, Any]) -> dict[str, Any]:
    parameters = request.get("parameters")
    return parameters if isinstance(parameters, dict) else {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _has_existing_domain_annotations(evidence: dict[str, Any]) -> bool:
    for example in evidence.get("examples", []):
        neighbor = example.get("neighbor_protein") or {}
        if neighbor.get("pfam") or neighbor.get("interpro"):
            return True
    return False


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _parse_interproscan_domains(tool_dir: Path, *, parse_interproscan_tsv: Callable[[str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    tsv_files = sorted(tool_dir.glob("*.tsv"))
    if not tsv_files:
        return []
    return parse_interproscan_tsv(tsv_files[0].read_text(encoding="utf-8"))
