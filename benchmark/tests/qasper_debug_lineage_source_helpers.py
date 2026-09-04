from __future__ import annotations

import hashlib
from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest
from benchmark.tests.qasper_debug_semantic_pack_fixtures import (
    _debug_source_input_snapshot,
)


def debug_source_packing(pack_identity: dict[str, str]) -> dict[str, Any]:
    text = "The paper uses the method."
    source_decisions = [
        {
            "source_item_index": 1,
            "evidence_id": "span:paper:s1",
            "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_chars": len(text),
            "decision": "packed",
            "reason": "packed",
            "semantic_rank": 1,
            "priority": [0, 1, 0, 0.0],
            "priority_factors": {"ranked_position": 0},
        }
    ]
    window_decisions = [
        {
            "stage": "window_selection",
            "evidence_id": "span:paper:s1",
            "selected": True,
            "decision": "selected",
            "reason": "full_source_within_limit",
        },
        {
            "stage": "fit_to_input_budget",
            "evidence_id": "span:paper:s1",
            "selected": True,
            "decision": "packed",
            "reason": "accepted_with_primary_window",
        },
    ]
    return {
        **_source_packing_fields(pack_identity, text),
        **_source_decision_fields(source_decisions, window_decisions),
        "source_input_snapshot": _debug_source_input_snapshot(
            text,
            route="fixture",
        ),
        "records": [
            {
                "evidence_id": "span:paper:s1",
                "text_digest": _fixture_digest(text),
                "selector_refs": ["E1:S1"],
                "source_selector_projection_trace": _selector_projection_trace(
                    "canonical_span_selector_projection.v1",
                    input_key="input_span_count",
                ),
            }
        ],
        "canonical_records": [
            {
                "evidence_id": "span:paper:s1",
                "text_digest": _fixture_digest(text),
                "selector_refs": ["E1:S1"],
                "candidate_selector_projection_trace": _selector_projection_trace(
                    "qasper_candidate_selector_projection.v1",
                    input_key="input_selector_count",
                ),
            }
        ],
        "selector_crosswalk": _selector_crosswalk(),
        "dropped_count": 0,
        "truncated_count": 0,
    }


def _source_packing_fields(
    pack_identity: dict[str, str],
    text: str,
) -> dict[str, Any]:
    return {
        "status": "passed",
        "contract_id": "qasper_source_packing_observation.v1",
        "semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "source_semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "source_records": [
            {
                "evidence_id": "span:paper:s1",
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "semantic_rank": 1,
                "selected_for_windowing": True,
                "packed": True,
                "stop_stage": "packed",
            }
        ],
    }


def _source_decision_fields(
    source_decisions: list[dict[str, Any]],
    window_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_decisions_complete": True,
        "source_input_count": len(source_decisions),
        "source_decision_count": len(source_decisions),
        "source_decisions_digest": _fixture_digest(source_decisions),
        "source_decisions": source_decisions,
        "window_decisions_complete": True,
        "window_selection_decision_count": 1,
        "selected_window_count": 1,
        "window_fit_decision_count": 1,
        "window_decision_count": len(window_decisions),
        "window_decisions_digest": _fixture_digest(window_decisions),
        "window_decisions": window_decisions,
    }


def _selector_projection_trace(
    contract_id: str,
    *,
    input_key: str,
) -> dict[str, Any]:
    decisions = [
        {
            "selector_id": "E1:S1",
            "selected": True,
            "decision": "selected_without_limit",
        }
    ]
    return {
        "contract_id": contract_id,
        "complete": True,
        input_key: 1,
        "selected_selector_count": 1,
        "decision_count": 1,
        "decisions_digest": _fixture_digest(decisions),
        "decisions": decisions,
    }


def _selector_crosswalk() -> dict[str, Any]:
    payload = {
        "contract_id": "qasper_selector_crosswalk.v1",
        "complete": True,
        "source_selector_count": 1,
        "canonical_selector_count": 1,
        "mapped_canonical_selector_count": 1,
        "source_selectors": [
            {
                "source_selector_ref": "E1:S1",
                "canonical_selector_refs": ["E1:S1"],
            }
        ],
        "canonical_selectors": [
            {
                "canonical_selector_ref": "E1:S1",
                "source_selector_refs": ["E1:S1"],
                "mapped": True,
            }
        ],
    }
    return {**payload, "crosswalk_digest": _fixture_digest(payload)}
