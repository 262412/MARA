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
        source_packing_observation={
            "contract_id": "qasper_source_packing_observation.v1",
            "source_records": [
                {
                    "evidence_id": "evidence-1",
                    "semantic_rank": 1,
                    "selected_for_windowing": True,
                    "packed": True,
                    "stop_stage": "packed",
                }
            ],
            "records": [
                {
                    "evidence_id": "evidence-1",
                    "selector_refs": ["E1:S1"],
                }
            ],
            "dropped_count": 0,
            "truncated_count": 0,
        },
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
                "event_subplans": [
                    {
                        "event_id": "event-1",
                        "span_refs": ["E1:S1"],
                        "slot_refs": {
                            "actor": ["E1:S1"],
                            "predicate": ["E1:S1"],
                            "object": ["E1:S1"],
                        },
                    }
                ],
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
    assert construction["authority_source"] == ("frozen_canonical_proposition_plan")
    assert construction["event_subplans"][0]["event_id"] == "event-1"
    assert lineage["source_packing"]["status"] == "passed"
    assert lineage["source_packing"]["source_records"][0]["stop_stage"] == ("packed")


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
    assert lineage["first_decisive_transition"]["stage"] == "plan_construction"
    assert lineage["first_decisive_transition"]["decision"] == (
        "no_legal_evidence_plan"
    )
    assert len(lineage["first_decisive_transition"]["decision_context_digest"]) == 64


def test_zero_plan_is_recorded_before_a_later_model_parse_failure() -> None:
    diagnostics: dict[str, Any] = {}
    stage = SimpleNamespace(
        value=None,
        attempts=[
            SimpleNamespace(
                response=SimpleNamespace(text='{"unexpected":"shape"}'),
                parse_failure_reason="plan_selection_schema_invalid",
                provider_failure_reason="",
            )
        ],
        provider_failure_reason="",
        failure_reason="plan_selection_schema_invalid",
        call_count=1,
    )
    record_proposal_data_lineage(
        diagnostics,
        stage,
        context=_context(),
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object"),
        allowed_proposition_slot_bindings={"E1:S1": ("actor", "predicate", "object")},
        allowed_proposition_evidence_plans={},
    )
    finalize_semantic_data_lineage(
        diagnostics,
        status="failed",
        reason="plan_selection_schema_invalid",
    )

    lineage = diagnostics["semantic_data_lineage"]
    assert lineage["first_inconsistency"]["stage"] == "plan_construction"
    assert lineage["first_inconsistency"]["reason"] == "no_legal_evidence_plan"
    assert lineage["proposal_attempts"][0]["parse_failure_reason"] == (
        "plan_selection_schema_invalid"
    )
    assert lineage["first_decisive_transition"]["stage"] == "plan_construction"


def test_unanswerable_with_a_legal_plan_records_the_candidate_plan_conflict() -> None:
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
        candidate="unanswerable",
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
                "required_object_tokens": ["systems", "two"],
                "covered_object_tokens": ["systems", "two"],
            }
        },
    )

    transition = diagnostics["semantic_data_lineage"]["first_decisive_transition"]
    assert transition["stage"] == "candidate_generation"
    assert transition["decision"] == "unanswerable_despite_legal_local_plan"
    assert transition["classification_hint"] == "candidate_plan_conflict"
    assert transition["decision_context"]["legal_plan_count"] == 1


def test_candidate_bound_audit_is_the_decisive_transition() -> None:
    diagnostics: dict[str, Any] = {}
    record_proposal_data_lineage(
        diagnostics,
        _stage({"candidate_judgment": "unknown", "canonical_evidence_plan_id": ""}),
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
            }
        },
    )
    diagnostics.update(
        audit_status="candidate_bound",
        audit_reason="candidate_relation_unknown",
    )

    finalize_semantic_data_lineage(
        diagnostics,
        status="parsed",
        reason="strict_schema_and_candidate_audit",
    )

    transition = diagnostics["semantic_data_lineage"]["first_decisive_transition"]
    assert transition["stage"] == "auditor_semantics"
    assert transition["decision"] == "candidate_bound"
    assert transition["classification_hint"] == "candidate_bound_terminal_abstention"
    assert transition["decision_context"]["audit_reason"] == (
        "candidate_relation_unknown"
    )
