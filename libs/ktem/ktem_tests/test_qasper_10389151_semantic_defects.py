from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan import (
    canonical_evidence_set_analysis,
    canonical_proposition_evidence_selection,
)
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
    proposition_evidence_bindings,
    typed_conclusion,
)
from ktem.docqa.semantic_relation_clause_validation import (
    premise_slot_evidence_for_audit,
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_semantic_entailment_audit import (
    semantic_entailment_audit_prompt,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "qasper_10389151_semantic_defects.json"
)
SAMPLE_A = "7cd22ca9e107d2b13a7cc94252aaa9007976b338"
SAMPLE_B = "6568a31241167f618ef5ede939053feaa2fb0d7e"


def _fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def _case(sample_id: str) -> dict[str, Any]:
    return _fixture()["cases"][sample_id]


def _selectors(case: dict[str, Any]) -> list[dict[str, Any]]:
    # The planner must be driven by the question and frozen selector payload,
    # never by the benchmark sample identity or its gold answer.
    return deepcopy(case["selectors"])


def _required_slots(question: str) -> tuple[str, ...]:
    return applicable_proposition_evidence_slots(build_question_proposition(question))


def _premises(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": selector["evidence_id"],
            "span_selector": selector["selector_id"],
            "quote": selector["text"],
            "span_start": selector["span_start"],
            "span_end": selector["span_end"],
            "binds_proposition_slots": selector["slot_hints"],
            "event_id": selector["event_id"],
            "object_tokens": selector["object_tokens"],
            "event_core_tokens": selector["event_core_tokens"],
            "predicate_match_kind": selector["predicate_match_kind"],
            "local_relation_state": selector["local_relation_state"],
            "semantic_alignment": selector["semantic_alignment"],
        }
        for selector in case["selectors"]
    ]


def test_10389151_a_auxiliary_learn_does_not_block_same_event_support() -> None:
    case = _case(SAMPLE_A)
    question = case["question"]
    selectors = _selectors(case)
    required_slots = _required_slots(question)

    for selector in selectors:
        assert selector["span_end"] - selector["span_start"] == len(selector["text"])
        assert selector["event_id"] == case["event_id"]

    analysis = canonical_evidence_set_analysis(
        question,
        selectors,
        required_slots,
        polarity_relation="proposition_support",
    )
    selection = canonical_proposition_evidence_selection(
        question,
        selectors,
        required_slots,
    )

    assert analysis["valid"] is True
    assert analysis["same_event"] is True
    assert analysis["event_ids"] == [case["event_id"]]
    assert analysis["required_object_tokens"] == tuple(
        case["expected"]["required_object_tokens"]
    )
    assert "learn" not in analysis["required_object_tokens"]
    assert selection.support is not None
    assert selection.contradiction is None
    assert [value["selector_id"] for value in selection.support] == case["expected"][
        "support_span_refs"
    ]

    support_plan = selection.plan.support_plan
    assert support_plan is not None
    assert support_plan.span_refs == tuple(case["expected"]["support_span_refs"])
    assert support_plan.event_subplans and len(support_plan.event_subplans) == 1
    assert support_plan.event_subplans[0].event_id == case["event_id"]
    assert support_plan.event_subplans[0].span_refs == tuple(
        case["expected"]["support_span_refs"]
    )
    assert support_plan.required_object_tokens == tuple(
        case["expected"]["required_object_tokens"]
    )
    assert support_plan.covered_object_tokens == support_plan.required_object_tokens


def test_10389151_b_composite_plan_projects_local_auditor_contributions() -> None:
    case = _case(SAMPLE_B)
    question = case["question"]
    selectors = _selectors(case)
    required_slots = _required_slots(question)
    proposition = build_question_proposition(question)

    assert {selector["event_id"] for selector in selectors} == {case["event_id"]}
    assert [selector["selector_id"] for selector in selectors] == case["expected"][
        "support_span_refs"
    ]
    assert (
        case["auditor_payload"]["premise_checks"]["P1"]["proposition_slot_checks"][
            "object"
        ]["binding_valid"]
        is False
    )
    assert (
        case["auditor_payload"]["premise_checks"]["P2"]["proposition_slot_checks"][
            "object"
        ]["binding_valid"]
        is False
    )

    selection = canonical_proposition_evidence_selection(
        question,
        selectors,
        required_slots,
    )
    premises = _premises(case)
    canonical_bindings = proposition_evidence_bindings(proposition)
    for premise in premises:
        premise["proposition_slot_bindings"] = {
            slot: canonical_bindings[slot]
            for slot in premise["binds_proposition_slots"]
        }
        premise["evidence_relation"] = "proposition_support"
    local_constraint = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        "yes",
        auditor_relationship="distinct_model",
    )
    slot_evidence = premise_slot_evidence_for_audit(local_constraint)
    prompt = semantic_entailment_audit_prompt(
        proposition,
        typed_conclusion(proposition, "yes"),
        "composite_conjunction",
        premises,
        original_candidate="yes",
        candidate_judgment="supported",
        premise_slot_evidence=slot_evidence,
    )
    payload = json.loads(prompt.split("AUDIT THIS PROOF PROPOSAL:\n", 1)[1])

    assert selection.support is not None
    assert selection.plan.support_plan is not None
    assert selection.plan.support_plan.span_refs == tuple(
        case["expected"]["support_span_refs"]
    )
    assert local_constraint["status"] == "passed"
    assert payload["target_proposition_slot_bindings"] == canonical_bindings
    assert payload["proof_mode"] == "composite_conjunction"
    for prompt_premise, source_premise in zip(payload["premises"], premises):
        assert "proposition_slot_bindings" not in prompt_premise
        contributions = prompt_premise["local_proposition_slot_contributions"]
        assert set(contributions) == set(source_premise["binds_proposition_slots"])
        assert contributions["object"]["text"] in source_premise["quote"]
        assert contributions["object"]["text"] != canonical_bindings["object"]
        assert prompt_premise["semantic_alignment"]["status"] == "verified"

    covered = {
        token
        for premise in payload["premises"]
        for token in premise["semantic_alignment"]["covered_object_tokens"]
    }
    assert covered == set(case["expected"]["required_object_tokens"])
