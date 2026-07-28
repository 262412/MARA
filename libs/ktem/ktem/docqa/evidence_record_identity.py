from __future__ import annotations

from typing import Any, Iterable

from .evidence_field_values import score_value
from .evidence_identity import canonicalize_and_dedupe_evidence, identity_of


def unique_evidence_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for record in records:
        try:
            identity = identity_of(record).key
        except ValueError:
            continue
        position = positions.get(identity)
        if position is None:
            positions[identity] = len(output)
            output.append(record)
            continue
        merged, _trace = canonicalize_and_dedupe_evidence([output[position], record])
        if len(merged) != 1:
            continue
        _merge_provenance(output[position], record, merged[0])
    return output


def _merge_provenance(
    target: dict[str, Any],
    duplicate: dict[str, Any],
    canonical: dict[str, Any],
) -> None:
    for key in (
        "source_backrefs",
        "retrieval_lineage",
        "representations",
        "duplicate_evidence_ids",
    ):
        if canonical.get(key):
            target[key] = list(canonical[key])
    target_metadata = dict(target.get("metadata") or {})
    target_metadata.update(dict(canonical.get("metadata") or {}))
    target["metadata"] = target_metadata
    for key, value in duplicate.items():
        if key == "scores" and isinstance(value, dict):
            scores = dict(target.get("scores") or {})
            scores.update(value)
            target["scores"] = scores
            continue
        if key == "score" or key.endswith("_score"):
            target[key] = max(score_value(target.get(key)), score_value(value))
            continue
        if target.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            target[key] = value
