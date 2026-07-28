from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import evidence_aliases, identity_of
from ktem.docqa.financial_table import parse_financial_table_cells


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
            if citation_id in _calculation_item_aliases(item):
                matched.append(item)
                break
    return matched


def record_calculation_stage_evidence(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> None:
    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        prediction["evidence_metadata"] = metadata
    metadata["used_evidence"] = list(items)
    metadata["cited_evidence"] = list(items)


def _calculation_item_aliases(item: dict[str, Any]) -> set[str]:
    aliases = evidence_aliases(item)
    for cell in parse_financial_table_cells(item):
        cell_item = dict(item)
        cell_item.pop("identity", None)
        cell_item.pop("canonical_id", None)
        cell_item["cell_id"] = cell.cell_id
        cell_item["evidence_level"] = "cell"
        aliases.add(identity_of(cell_item).key)
    return aliases


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
