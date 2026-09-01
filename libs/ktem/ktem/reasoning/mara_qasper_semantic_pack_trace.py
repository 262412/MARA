from __future__ import annotations

from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest


def canonical_selector_projection_trace(
    records: list[dict[str, Any]],
    projected: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    observation: dict[str, Any],
    selected_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_canonical_selector_projection.v1",
        "complete": True,
        "input_record_count": len(records),
        "output_record_count": len(projected),
        "input_selector_count": len(decisions),
        "selected_selector_count": len(selected_identities),
        "decision_count": len(decisions),
        "selector_universe_refs": [
            str(selector.get("selector_id") or "")
            for record in projected
            for selector in record.get("selectors") or []
        ],
        "selected_plan_refs": [
            str(value).strip()
            for value in observation.get("evidence_refs") or []
            if str(value).strip()
        ],
        "decisions_digest": canonical_payload_digest(decisions),
        "decisions": decisions,
    }
