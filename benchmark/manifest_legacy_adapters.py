from __future__ import annotations

from pathlib import Path
from typing import Any

from .financebench_evidence import legacy_financebench_evidence_from_source


def legacy_evidence_from_source(
    value: str,
    *,
    dataset_name: str,
    record: dict[str, Any],
    document_id: str,
    document_path: Path | None = None,
) -> dict[str, Any] | None:
    adapter = _evidence_adapter_name(record, dataset_name)
    if adapter != "financebench":
        return None
    return legacy_financebench_evidence_from_source(
        value,
        document_id=document_id,
        document_path=document_path,
    )


def _evidence_adapter_name(record: dict[str, Any], dataset_name: str) -> str:
    for value in (
        record.get("evidence_adapter"),
        record.get("domain_adapter"),
        _metadata_value(record, "evidence_adapter"),
        _metadata_value(record, "domain_adapter"),
    ):
        adapter = str(value or "").strip().lower()
        if adapter:
            return adapter

    normalized_dataset = str(dataset_name or "").strip().lower()
    if normalized_dataset.startswith("financebench"):
        return "financebench"
    return ""


def _metadata_value(record: dict[str, Any], key: str) -> Any:
    metadata = record.get("metadata")
    return metadata.get(key) if isinstance(metadata, dict) else None
