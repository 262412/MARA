from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.reasoning.mara_semantic_proposition_data_lineage import (
    finalize_semantic_data_lineage,
    record_proposal_data_lineage,
)


def _context() -> SimpleNamespace:
    question = "Did the authors compare the two systems?"
    text = "The authors compared the two systems."
    return SimpleNamespace(
        question=question,
        packed=[
            {
                "evidence_id": "evidence-1",
                "selectors": [
                    {
                        "selector_id": "E1:S1",
                        "text": text,
                        "span_start": 0,
                        "span_end": len(text),
                        "allowed_proposition_slots": [
                            "actor",
                            "predicate",
                            "object",
                        ],
                        "object_tokens": ["two", "systems"],
                        "event_id": "event-1",
                    }
                ],
            }
        ],
        slots=[{"slot_id": "support:boolean_proposition"}],
        semantic_pack_digest="pack-digest",
        canonical_span_universe_digest="span-digest",
        candidate_transaction_id="candidate-transaction",
    )


def _stage(value: dict[str, Any] | None) -> SimpleNamespace:
    return SimpleNamespace(
        value=value,
        attempts=[],
        provider_failure_reason="",
        failure_reason="",
        call_count=1,
    )


def test_lineage_records_selector_and_plan_construction_trace() -> None:
    diagnostics: dict[str, Any] = {}
    record_proposal_data_lineage(
        diagnostics,
        _stage({"canonical_evidence_plan_id": "plan-1"}),
        context=_context(),
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object"),
        allowed_proposition_slot_bindings={"E1:S1": ("actor", "predicate", "object")},
        allowed_proposition_evidence_plans={
            "plan-1": {
                "plan_id": "plan-1",
                "polarity_relation": "proposition_support",
                "span_refs": ["E1:S1"],
                "slot_refs": {
                    "actor": ["E1:S1"],
                    "predicate": ["E1:S1"],
                    "object": ["E1:S1"],
                },
                "event_binding_id": "event-1",
                "required_object_tokens": ["systems", "two"],
                "covered_object_tokens": ["systems", "two"],
            }
        },
    )

    lineage = diagnostics["semantic_data_lineage"]
    selector = lineage["selector"]
    construction = lineage["plan_construction"]
    assert selector["universe_refs"] == ["E1:S1"]
    assert selector["candidate_count"] == 1
    assert selector["event_ids"] == ["event-1"]
    assert construction["transport_status"] == "passed"
    assert construction["semantic_plan_status"] == "passed"
    assert construction["candidate_count"] >= 1
    assert construction["required_slots"] == ["actor", "predicate", "object"]
    assert construction["covered_slots"] == ["actor", "predicate", "object"]
    assert construction["event_ids"] == ["event-1"]


def test_unambiguous_answerable_zero_plan_cannot_finalize_lineage_as_passed() -> None:
    diagnostics: dict[str, Any] = {}
    record_proposal_data_lineage(
        diagnostics,
        _stage(
            {
                "candidate_judgment": "unknown",
                "canonical_evidence_plan_id": "",
            }
        ),
        context=_context(),
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object"),
        allowed_proposition_slot_bindings={"E1:S1": ("actor", "predicate", "object")},
        allowed_proposition_evidence_plans={},
    )

    finalize_semantic_data_lineage(
        diagnostics,
        status="parsed",
        reason="strict_schema_and_candidate_audit",
    )

    lineage = diagnostics["semantic_data_lineage"]
    assert lineage["plan_construction"]["transport_status"] == "passed"
    assert lineage["plan_construction"]["semantic_plan_status"] == "failed"
    assert lineage["plan_construction"]["reason"] == "no_legal_evidence_plan"
    assert lineage["status"] == "failed"
    assert lineage["first_inconsistency"]["stage"] == "plan_construction"
