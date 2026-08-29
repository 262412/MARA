from __future__ import annotations

import json
from typing import Any

from jsonschema import validate
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set
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
    assert binding["polarity_signal"] in {"conflict", "ambiguous"}


def test_absent_support_and_contradiction_remain_unresolved() -> None:
    context = _full_record(
        "context-source",
        "C:S1",
        "The paper discusses comparisons between systems.",
    )

    binding = candidate_evidence_set_binding([context], QUESTION)

    assert binding["support"] is False
    assert binding["explicit_contradiction"] is False
    assert binding["polarity_signal"] == "unresolved"


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
