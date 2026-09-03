from __future__ import annotations

from typing import Any

import pytest
from ktem.reasoning import (
    mara_qasper_candidate_selector_projection as selector_projection_module,
)
from ktem.reasoning import mara_qasper_semantic_pack as semantic_pack_module
from ktem.reasoning.mara_qasper_candidate_selector_projection import (
    _candidate_selectors_from_options,
    prioritized_candidate_prompt_evidence,
)
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records


def _selector(selector_id: str, text: str) -> dict[str, Any]:
    return {
        "selector_id": selector_id,
        "text": text,
        "span_start": 0,
        "span_end": len(text),
    }


def test_prepare_canonical_records_propagates_candidate_transaction_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    original = semantic_pack_module.candidate_evidence_set_binding

    def recording_binding(
        records: list[dict[str, Any]],
        question: str,
        *,
        candidate_transaction_id: str = "",
    ) -> dict[str, Any]:
        observed.append(candidate_transaction_id)
        return original(
            records,
            question,
            candidate_transaction_id=candidate_transaction_id,
        )

    monkeypatch.setattr(
        semantic_pack_module,
        "candidate_evidence_set_binding",
        recording_binding,
    )

    prepare_qasper_canonical_records(
        "Did the authors compare the two systems?",
        [
            {
                "evidence_id": "evidence-1",
                "text": "The authors compared the two systems",
                "selectors": [
                    _selector("E1:S1", "The authors compared the two systems")
                ],
            }
        ],
        candidate_transaction_id="candidate-transaction-1",
    )

    assert observed == ["candidate-transaction-1"]


def test_candidate_selector_projection_reuses_candidate_transaction_for_local_plans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, int]] = []
    original = selector_projection_module.prepare_qasper_canonical_records_with_trace

    def recording_prepare(
        question: str,
        records: list[dict[str, Any]],
        *,
        candidate_transaction_id: str = "",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        observed.append((candidate_transaction_id, len(records)))
        return original(
            question,
            records,
            candidate_transaction_id=candidate_transaction_id,
        )

    monkeypatch.setattr(
        selector_projection_module,
        "prepare_qasper_canonical_records_with_trace",
        recording_prepare,
    )

    question = "Did the authors compare the two systems?"
    records = [
        {
            "evidence_id": f"evidence-{index}",
            "label": f"E{index}",
            "text": "The authors compared the two systems.",
            "text_start": 0,
            "candidate_source_text": "The authors compared the two systems.",
            "candidate_source_text_start": 0,
            "canonical_start": None,
            "selectors": [],
        }
        for index in (1, 2)
    ]

    prioritized_candidate_prompt_evidence(
        records,
        question,
        candidate_transaction_id="candidate-transaction-1",
    )

    assert observed == [
        ("candidate-transaction-1", 1),
        ("candidate-transaction-1", 1),
    ]


def test_candidate_selector_projection_retains_typed_planner_metadata() -> None:
    [selector] = _candidate_selectors_from_options(
        [
            {
                "evidence_ref": "E1:S1",
                "text": "The authors compared the two systems",
                "span_start": 0,
                "span_end": 36,
                "evidence_id": "evidence-1",
                "event_id": "event-1",
                "object_tokens": ["system"],
                "predicate_match_kind": "exact",
                "allowed_proposition_slots": ["actor", "predicate", "object"],
                "proposition_slot_spans": {"object": {"text": "the two systems"}},
            }
        ]
    )

    assert selector["event_id"] == "event-1"
    assert selector["object_tokens"] == ["system"]
    assert selector["predicate_match_kind"] == "exact"
    assert selector["allowed_proposition_slots"] == [
        "actor",
        "predicate",
        "object",
    ]
