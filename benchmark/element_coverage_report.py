from __future__ import annotations

from typing import Any


def element_coverage_report(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total_records = 0
    with_index = 0
    records_by_modality: dict[str, int] = {}
    records_by_source: dict[str, int] = {}
    missing_example_ids = []

    for prediction in predictions:
        records = _element_records(prediction)
        if records:
            with_index += 1
        else:
            missing_example_ids.append(str(prediction.get("example_id") or ""))
        for record in records:
            total_records += 1
            _increment(records_by_modality, _record_modality(record))
            _increment(records_by_source, _record_source(record))

    return {
        "total_predictions": len(predictions),
        "predictions_with_element_index": with_index,
        "predictions_without_element_index": len(predictions) - with_index,
        "total_element_index_records": total_records,
        "records_by_modality": dict(sorted(records_by_modality.items())),
        "records_by_source": dict(sorted(records_by_source.items())),
        "missing_example_ids": missing_example_ids,
    }


def _element_records(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    return [dict(item) for item in metadata.get("element_index") or []]


def _record_modality(record: dict[str, Any]) -> str:
    return str(record.get("modality") or record.get("element_type") or "unknown")


def _record_source(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        return "unknown"
    return str(metadata.get("index_source") or metadata.get("source") or "unknown")


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1
