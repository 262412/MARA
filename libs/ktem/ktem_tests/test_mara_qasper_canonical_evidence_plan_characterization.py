from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_candidate_evidence import candidate_evidence_set_binding
from ktem.reasoning.mara_qasper_candidate_evidence_sets import candidate_span_set
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

QUESTION = "Did the authors compare the two systems?"
SLOT_ID = "support:boolean_proposition"


def _applicable_slots(question: str) -> tuple[str, ...]:
    proposition = build_question_proposition(question)
    return tuple(
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if slot != "quantifier" or proposition.quantifier != "none"
    )


def _candidate_selector(
    selector_id: str,
    text: str,
    start: int,
    *,
    event_id: str,
    slot_hints: tuple[str, ...],
    object_tokens: set[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_id": "paper",
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
        "slot_hints": list(slot_hints),
        "object_tokens": sorted(
            object_tokens
            if object_tokens is not None
            else semantic_content_token_set(text)
        ),
        "event_id": event_id,
    }


def _split_plan_selectors(
    *,
    first_event: str,
    second_event: str,
    first_selector_id: str = "E1:S1",
    second_selector_id: str = "E1:S2",
) -> list[dict[str, Any]]:
    return [
        _candidate_selector(
            first_selector_id,
            "The authors compared",
            0,
            event_id=first_event,
            slot_hints=("actor", "predicate"),
        ),
        _candidate_selector(
            second_selector_id,
            "the two systems",
            30,
            event_id=second_event,
            slot_hints=("object", "quantifier"),
        ),
    ]


def _full_record(evidence_id: str, selector_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "text": text,
        "selectors": [
            {
                "selector_id": selector_id,
                "text": text,
                "span_start": 0,
                "span_end": len(text),
            }
        ],
    }


def _natural_plan(
    *,
    first_event: str = "event-1",
    second_event: str = "event-1",
) -> dict[str, Any]:
    selectors = _split_plan_selectors(
        first_event=first_event,
        second_event=second_event,
    )
    allowed_bindings = {
        selector["selector_id"]: tuple(selector["slot_hints"]) for selector in selectors
    }
    packed = [
        {
            "evidence_id": "paper",
            "selectors": [
                {
                    key: selector[key]
                    for key in (
                        "selector_id",
                        "text",
                        "span_start",
                        "span_end",
                        "event_id",
                    )
                }
                for selector in selectors
            ],
        }
    ]
    payload = {
        "candidate_judgment": "supported",
        "support_mode": "evidence_set",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": selector["selector_id"],
                "proposition_fragment": selector["text"],
                "supports_slot_ids": [SLOT_ID],
                "binds_proposition_slots": list(selector["slot_hints"]),
            }
            for selector in selectors
        ],
        "not_applicable_proposition_slots": [],
    }
    return {
        "question": QUESTION,
        "selectors": selectors,
        "packed": packed,
        "payload": payload,
        "allowed_bindings": allowed_bindings,
        "applicable_slots": _applicable_slots(QUESTION),
    }


def _schema_and_parse(plan: dict[str, Any]) -> Any:
    response_format = semantic_proposition_response_format(
        list(plan["allowed_bindings"]),
        [SLOT_ID],
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
    )
    schema = response_format["json_schema"]["schema"]
    validate(instance=plan["payload"], schema=schema)
    return parse_semantic_proposition_response(
        json.dumps(plan["payload"]),
        packed=plan["packed"],
        slot_ids={SLOT_ID},
        model="characterization-model",
        seed=17,
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
    )


def test_same_source_different_event_slots_are_not_concatenated() -> None:
    selectors = _split_plan_selectors(
        first_event="collection-event",
        second_event="comparison-event",
    )

    selected = candidate_span_set(
        QUESTION,
        selectors,
        _applicable_slots(QUESTION),
        polarity="yes",
    )

    assert selected is None


def test_four_token_object_requires_complete_coverage() -> None:
    question = "Did the authors collect Alpha Beta Gamma Delta?"
    selectors = [
        _candidate_selector(
            "E1:S1",
            "The authors collected",
            0,
            event_id="collection-event",
            slot_hints=("actor", "predicate"),
        ),
        _candidate_selector(
            "E1:S2",
            "Alpha Beta",
            30,
            event_id="collection-event",
            slot_hints=("object",),
        ),
    ]

    assert semantic_content_token_set(
        build_question_proposition(question).object_surface
    ) == {"alpha", "beta", "gamma", "delta"}
    selected = candidate_span_set(
        question,
        selectors,
        _applicable_slots(question),
        polarity="yes",
    )

    assert selected is None


def test_selector_does_not_return_sorted_first_valid_semantically_weaker_set() -> None:
    selectors = [
        *_split_plan_selectors(
            first_event="poor-event-a",
            second_event="poor-event-b",
            first_selector_id="A:S1",
            second_selector_id="A:S2",
        ),
        *_split_plan_selectors(
            first_event="complete-event",
            second_event="complete-event",
            first_selector_id="Z:S1",
            second_selector_id="Z:S2",
        ),
    ]

    selected = candidate_span_set(
        QUESTION,
        selectors,
        _applicable_slots(QUESTION),
        polarity="yes",
    )

    assert selected is not None
    assert [selector["selector_id"] for selector in selected] == ["Z:S1", "Z:S2"]
    assert {selector["event_id"] for selector in selected} == {"complete-event"}


def test_support_and_contradiction_have_conflict_polarity_state() -> None:
    support = _full_record(
        "support-source",
        "S:S1",
        "The authors compared the two systems.",
    )
    contradiction = _full_record(
        "contradiction-source",
        "C:S1",
        "The authors did not compare the two systems.",
    )

    binding = candidate_evidence_set_binding([support, contradiction], QUESTION)

    assert binding["support"] is True
    assert binding["explicit_contradiction"] is True
    assert binding["binding_state"] == "ambiguous_conflict"
    assert binding["polarity_signal"] == "undetermined"


def test_absent_support_and_contradiction_remain_unresolved() -> None:
    context = _full_record(
        "context-source",
        "C:S1",
        "The paper discusses comparisons between systems.",
    )

    binding = candidate_evidence_set_binding([context], QUESTION)

    assert binding["support"] is False
    assert binding["explicit_contradiction"] is False
    assert binding["binding_state"] == "unresolved"
    assert binding["polarity_signal"] == "undetermined"


def test_schema_accepted_natural_plan_is_parser_accepted() -> None:
    parsed = _schema_and_parse(_natural_plan())

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert parsed.value["proof_mode"] == "composite_conjunction"
    assert {
        slot
        for premise in parsed.value["premises"]
        for slot in premise["binds_proposition_slots"]
    } == set(_applicable_slots(QUESTION))


def test_complete_slot_union_without_object_event_binding_cannot_be_authority() -> None:
    plan = _natural_plan(first_event="event-a", second_event="event-b")
    parsed = _schema_and_parse(plan)

    # The provider-facing schema and local parser only see a complete union of
    # declared slots here.  Authority must still reject the two event fragments.
    assert parsed.failure_reason == ""
    assert parsed.value is not None
    selected = candidate_span_set(
        plan["question"],
        plan["selectors"],
        plan["applicable_slots"],
        polarity="yes",
    )

    assert selected is None


def test_schema_rejects_non_unknown_incomplete_slot_union() -> None:
    plan = _natural_plan(first_event="event-a", second_event="event-b")
    incomplete_selector = plan["selectors"][1]
    incomplete_selector["slot_hints"] = ["object"]
    plan["allowed_bindings"][incomplete_selector["selector_id"]] = ("object",)
    plan["payload"]["premises"][1]["binds_proposition_slots"] = ["object"]

    response_format = semantic_proposition_response_format(
        list(plan["allowed_bindings"]),
        [SLOT_ID],
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
    )
    schema = response_format["json_schema"]["schema"]

    parsed = parse_semantic_proposition_response(
        json.dumps(plan["payload"]),
        packed=plan["packed"],
        slot_ids={SLOT_ID},
        model="characterization-model",
        seed=17,
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
    )
    assert parsed.value is None
    assert parsed.failure_reason == "proposition_slot_coverage_incomplete"

    # Schema acceptance must imply parser acceptance for this structural rule.
    with pytest.raises(ValidationError):
        validate(instance=plan["payload"], schema=schema)


def test_schema_and_parser_select_the_same_complete_evidence_plan() -> None:
    plan = _natural_plan()
    plan_id = "complete-support-plan"
    allowed_plans = {
        plan_id: {
            "plan_id": plan_id,
            "polarity_relation": "proposition_support",
            "span_refs": list(plan["allowed_bindings"]),
        }
    }
    response_format = semantic_proposition_response_format(
        list(plan["allowed_bindings"]),
        [SLOT_ID],
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
        allowed_proposition_evidence_plans=allowed_plans,
    )
    validate(
        instance=plan["payload"],
        schema=response_format["json_schema"]["schema"],
    )

    parsed = parse_semantic_proposition_response(
        json.dumps(plan["payload"]),
        packed=plan["packed"],
        slot_ids={SLOT_ID},
        model="characterization-model",
        seed=17,
        candidate="yes",
        applicable_proposition_slots=plan["applicable_slots"],
        allowed_proposition_slot_bindings=plan["allowed_bindings"],
        allowed_proposition_evidence_plans=allowed_plans,
    )

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert parsed.value["canonical_evidence_plan_id"] == plan_id


def test_downstream_constraint_reuses_canonical_event_predicate() -> None:
    proposition = build_question_proposition(QUESTION)
    premises = [
        {
            "evidence_id": selector["evidence_id"],
            "span_selector": selector["selector_id"],
            "quote": selector["text"],
            "span_start": selector["span_start"],
            "span_end": selector["span_end"],
            "binds_proposition_slots": selector["slot_hints"],
            "event_id": selector["event_id"],
            "object_tokens": selector["object_tokens"],
            "event_core_tokens": selector["object_tokens"],
            "predicate_match_kind": (
                "exact" if "predicate" in selector["slot_hints"] else "missing"
            ),
            "local_relation_state": "affirmative_assertion",
        }
        for selector in _split_plan_selectors(
            first_event="event-a",
            second_event="event-b",
        )
    ]

    constraint = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        "yes",
        auditor_relationship="distinct_model",
    )

    assert constraint["status"] == "rejected"
    assert constraint["reason"] == "local_semantic_event_binding_inconsistent"
