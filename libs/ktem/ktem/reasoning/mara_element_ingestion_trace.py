from __future__ import annotations

from typing import Any


def element_ingestion_trace(
    pipeline: Any,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    direct = getattr(pipeline, "element_ingestion_trace", None)
    traces = [dict(direct)] if isinstance(direct, dict) else []
    traces.extend(
        dict(trace)
        for record in records
        for metadata in [record.get("metadata")]
        if isinstance(metadata, dict)
        for trace in [metadata.get("element_ingestion_trace")]
        if isinstance(trace, dict)
    )
    if not traces:
        return _trace_payload(records, [])
    conflicts: list[dict[str, Any]] = []
    for trace in traces:
        for conflict in trace.get("identity_conflicts") or []:
            if isinstance(conflict, dict) and conflict not in conflicts:
                conflicts.append(dict(conflict))
    return _trace_payload(records, conflicts)


def _trace_payload(
    records: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "element_ingestion_status": "partial" if conflicts else "complete",
        "accepted_record_count": len(records),
        "rejected_record_count": len(conflicts),
        "identity_conflict_count": len(conflicts),
        "identity_conflicts": conflicts,
    }
