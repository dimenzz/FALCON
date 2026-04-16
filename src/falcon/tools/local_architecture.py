from __future__ import annotations

from collections import defaultdict
from typing import Any


def probe_local_sequence_architecture(
    *,
    sequence: str,
    min_repeat_unit_length: int = 4,
    max_repeat_unit_length: int = 12,
    min_copy_count: int = 2,
) -> dict[str, Any]:
    cleaned = "".join(base for base in str(sequence).upper() if base in {"A", "C", "G", "T", "N"})
    features = _direct_repeat_features(
        sequence=cleaned,
        min_repeat_unit_length=max(1, int(min_repeat_unit_length)),
        max_repeat_unit_length=max(1, int(max_repeat_unit_length)),
        min_copy_count=max(2, int(min_copy_count)),
    )
    summary = {
        "repeat_feature_count": len(features),
        "direct_repeat_present": any(feature["feature_type"] == "direct_repeat" for feature in features),
        "inverted_repeat_present": any(feature["feature_type"] == "inverted_repeat" for feature in features),
        "periodic_repeat_array_present": any(feature["feature_type"] == "periodic_repeat_array" for feature in features),
    }
    return {"features": features, "summary": summary}


def _direct_repeat_features(
    *,
    sequence: str,
    min_repeat_unit_length: int,
    max_repeat_unit_length: int,
    min_copy_count: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
    sequence_length = len(sequence)
    for unit_length in range(min_repeat_unit_length, min(max_repeat_unit_length, sequence_length) + 1):
        for start in range(0, sequence_length - unit_length + 1):
            unit = sequence[start : start + unit_length]
            grouped[(unit, unit_length)].append(start)
    features: list[dict[str, Any]] = []
    for (unit, unit_length), starts in grouped.items():
        unique_starts = sorted(set(starts))
        if len(unique_starts) < min_copy_count:
            continue
        feature_type = "periodic_repeat_array" if _is_periodic(unique_starts) else "direct_repeat"
        features.append(
            {
                "feature_type": feature_type,
                "start": unique_starts[0] + 1,
                "end": unique_starts[-1] + unit_length,
                "repeat_unit_length": unit_length,
                "copy_count": len(unique_starts),
                "score": float(len(unique_starts) * unit_length),
                "consensus_or_unit_snippet": unit,
            }
        )
    features.sort(key=lambda item: (-item["score"], item["start"], item["repeat_unit_length"]))
    return features[:25]


def _is_periodic(starts: list[int]) -> bool:
    if len(starts) < 3:
        return False
    deltas = [right - left for left, right in zip(starts, starts[1:])]
    return len(set(deltas)) == 1
