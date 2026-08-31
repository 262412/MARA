from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest


def project_qasper_canonical_selector_trace(
    trace: dict[str, Any],
    *,
    source_record_count: int,
    selected_indices: list[int],
    rejection_reason: str,
) -> dict[str, Any]:
    """Project selector decisions through one occurrence-sensitive record drop."""

    decisions = deepcopy(trace.get("decisions"))
    if (
        trace.get("contract_id") != "qasper_canonical_selector_projection.v1"
        or trace.get("complete") is not True
        or trace.get("output_record_count") != source_record_count
        or not isinstance(decisions, list)
    ):
        raise ValueError("canonical_selector_projection_occurrence_mismatch")
    source_indices = list(
        dict.fromkeys(
            int(decision.get("record_index") or 0)
            for decision in decisions
            if isinstance(decision, dict) and decision.get("decision") == "selected"
        )
    )
    if (
        len(source_indices) != source_record_count
        or any(index < 0 or index >= source_record_count for index in selected_indices)
        or len(set(selected_indices)) != len(selected_indices)
    ):
        raise ValueError("canonical_selector_projection_occurrence_mismatch")
    retained_source_indices = {source_indices[index] for index in selected_indices}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("canonical_selector_projection_occurrence_mismatch")
        if (
            decision.get("decision") == "selected"
            and int(decision.get("record_index") or 0) not in retained_source_indices
        ):
            decision["decision"] = "rejected"
            decision["reason"] = rejection_reason
    return {
        **deepcopy(trace),
        "output_record_count": len(selected_indices),
        "selected_selector_count": sum(
            decision.get("decision") == "selected" for decision in decisions
        ),
        "decision_count": len(decisions),
        "decisions_digest": canonical_payload_digest(decisions),
        "decisions": decisions,
    }
