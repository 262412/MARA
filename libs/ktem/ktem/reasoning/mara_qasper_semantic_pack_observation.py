from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest

from .mara_qasper_selector_lineage import qasper_selector_crosswalk


def source_packing_observation(
    packing: Any,
    *,
    canonical_records: list[dict[str, Any]],
    canonical_semantic_pack_digest: str,
) -> dict[str, Any]:
    """Build the immutable observation of source and window packing."""

    window_counts = _window_decision_counts(packing.window_decisions)
    return {
        "contract_id": "qasper_source_packing_observation.v1",
        "semantic_pack_digest": canonical_semantic_pack_digest,
        "source_semantic_pack_digest": packing.semantic_pack_digest,
        "source_input_snapshot": deepcopy(packing.source_input_snapshot),
        "record_count": len(packing.records),
        "selector_count": sum(
            len(record.get("selectors") or []) for record in packing.records
        ),
        "estimated_input_tokens": packing.estimated_input_tokens,
        "input_token_budget": packing.input_token_budget,
        "item_char_limit": packing.item_char_limit,
        "dropped_count": packing.dropped_count,
        "truncated_count": packing.truncated_count,
        "source_records": deepcopy(packing.source_records),
        "source_decisions_complete": bool(packing.source_decisions),
        "source_input_count": len(packing.source_decisions),
        "source_decision_count": len(packing.source_decisions),
        "source_decisions_digest": canonical_payload_digest(packing.source_decisions),
        "source_decisions": deepcopy(packing.source_decisions),
        "window_decisions_complete": bool(
            packing.window_decisions
            and window_counts["window_fit"] == window_counts["selected"]
        ),
        "window_selection_decision_count": window_counts["selection"],
        "selected_window_count": window_counts["selected"],
        "window_fit_decision_count": window_counts["window_fit"],
        "window_decision_count": len(packing.window_decisions),
        "window_decisions_digest": canonical_payload_digest(packing.window_decisions),
        "window_decisions": deepcopy(packing.window_decisions),
        "records": _record_summaries(packing.records, canonical=False),
        "canonical_records": _record_summaries(canonical_records, canonical=True),
        "selector_crosswalk": qasper_selector_crosswalk(
            packing.records,
            canonical_records,
        ),
    }


def _window_decision_counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "selection": sum(
            decision.get("stage") == "window_selection" for decision in decisions
        ),
        "selected": sum(
            decision.get("stage") == "window_selection"
            and decision.get("selected") is True
            for decision in decisions
        ),
        "window_fit": sum(
            decision.get("stage") == "fit_to_input_budget" for decision in decisions
        ),
    }


def _record_summaries(
    records: list[dict[str, Any]],
    *,
    canonical: bool,
) -> list[dict[str, Any]]:
    return [_record_summary(record, canonical=canonical) for record in records]


def _record_summary(
    record: dict[str, Any],
    *,
    canonical: bool,
) -> dict[str, Any]:
    summary = {
        "evidence_id": str(record.get("evidence_id") or ""),
        "label": str(record.get("label") or ""),
        "text_start": record.get("text_start"),
        "text_digest": canonical_payload_digest(str(record.get("text") or "")),
        "selector_refs": [
            str(selector.get("selector_id") or "")
            for selector in record.get("selectors") or []
            if isinstance(selector, dict)
        ],
    }
    if not canonical:
        summary["window_index"] = record.get("window_index")
        summary["source_selector_projection_trace"] = deepcopy(
            record.get("source_selector_projection_trace") or {}
        )
    else:
        summary["candidate_selector_projection_trace"] = deepcopy(
            record.get("candidate_selector_projection_trace") or {}
        )
    return summary


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def mapping_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) else []


def source_records_from_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]] | None:
    observation = payload.get("source_packing_observation")
    if not isinstance(observation, dict) or (
        observation.get("contract_id") != "qasper_source_packing_observation.v1"
        or observation.get("semantic_pack_digest")
        != payload.get("semantic_pack_digest")
        or not str(observation.get("source_semantic_pack_digest") or "")
    ):
        return None
    records = observation.get("source_records")
    if not isinstance(records, list) or not all(
        isinstance(value, dict) for value in records
    ):
        return None
    return records
