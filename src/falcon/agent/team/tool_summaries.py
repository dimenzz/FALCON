from __future__ import annotations

from typing import Any

from falcon.tools.manifest import ToolManifest


def summarize_tool_results(
    *,
    tool_results: list[dict[str, Any]],
    tool_manifest: ToolManifest,
    existing_summaries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    existing_summaries = existing_summaries or []
    summaries = [_summarize_result(result=result, spec=tool_manifest.get(str(result.get("tool") or ""))) for result in tool_results]
    return _apply_lifecycle(existing_summaries=existing_summaries, new_summaries=summaries)


def _summarize_result(*, result: dict[str, Any], spec: Any) -> dict[str, Any]:
    tool = str(result.get("tool") or "unknown")
    status = str(result.get("status") or "unknown")
    summary_type = getattr(spec, "evidence_type", tool)
    payload: dict[str, Any] = {
        "tool": tool,
        "status": status,
        "summary_type": summary_type,
        "request_id": result.get("request_id"),
        "raw_observation_ref": result.get("evidence_ref"),
        "addresses": [result["evidence_need_id"]] if result.get("evidence_need_id") else [],
        "lifecycle": "active",
    }
    if status in {"rejected", "error"}:
        payload["lifecycle"] = "invalid"
        payload["summary"] = {"reason": result.get("reason"), "status": status}
        return payload
    if tool == "run_candidate_mmseqs":
        hits = result.get("hits") or []
        top_hit = hits[0] if hits else {}
        payload["summary_type"] = "candidate_homology"
        payload["summary"] = {
            "hit_count": len(hits),
            "top_hit_target_id": top_hit.get("target_id"),
            "top_hit_bits": top_hit.get("bits"),
        }
        return payload
    if tool == "run_interproscan":
        domains = result.get("domains") or []
        payload["summary_type"] = "candidate_domain_annotation"
        payload["summary"] = {
            "domain_count": len(domains),
            "domain_ids": sorted(
                {
                    str(domain.get("accession") or domain.get("id") or "")
                    for domain in domains
                    if str(domain.get("accession") or domain.get("id") or "")
                }
            ),
        }
        return payload
    if tool == "query_context_features":
        payload["summary"] = dict(result.get("summary") or {})
        return payload
    if tool == "search_literature":
        payload["summary_type"] = "literature_search"
        payload["summary"] = {"record_count": len(result.get("records") or [])}
        return payload
    if tool == "local_sequence_architecture_probe":
        payload["summary_type"] = "local_sequence_architecture"
        payload["summary"] = dict(result.get("summary") or {})
        return payload
    payload["summary"] = {"status": status}
    return payload


def _apply_lifecycle(*, existing_summaries: list[dict[str, Any]], new_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_keys = {(item.get("tool"), tuple(item.get("addresses") or []), item.get("summary_type")) for item in new_summaries}
    for existing in existing_summaries:
        if existing.get("lifecycle") != "active":
            continue
        key = (existing.get("tool"), tuple(existing.get("addresses") or []), existing.get("summary_type"))
        if key in seen_keys:
            existing["lifecycle"] = "superseded"
    return new_summaries
