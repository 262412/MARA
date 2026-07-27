from __future__ import annotations

from typing import Any


def calculation_citation_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    citation_ids = _calculation_citation_ids(prediction)
    if not citation_ids:
        return []
    matched: list[dict[str, Any]] = []
    for citation_id in citation_ids:
        for item in candidates:
            item_ids = {
                str(item.get(field) or "").strip()
                for field in (
                    "evidence_id",
                    "cell_id",
                    "canonical_id",
                    "element_id",
                )
            }
            if citation_id in item_ids:
                matched.append(item)
                break
    return matched


def _calculation_citation_ids(prediction: dict[str, Any]) -> list[str]:
    evidence_bundle = prediction.get("evidence_bundle")
    bundle = evidence_bundle if isinstance(evidence_bundle, dict) else {}
    evidence_metadata = prediction.get("evidence_metadata")
    metadata = evidence_metadata if isinstance(evidence_metadata, dict) else {}
    trace_containers = [
        metadata,
        dict(bundle.get("metadata") or {}),
        bundle,
    ]
    for container in trace_containers:
        trace = dict(container.get("finance_numeric_trace") or {})
        execution = dict(trace.get("calculation_execution") or {})
        if execution.get("status") != "ok":
            continue
        return list(
            dict.fromkeys(
                str(citation_id).strip()
                for citation_id in execution.get("citation_ids") or []
                if str(citation_id or "").strip()
            )
        )
    return []
