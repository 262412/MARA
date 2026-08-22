from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.query_plan_schema import (
    EvidenceSlot,
    evidence_slot_references_are_bound,
)
from ktem.docqa.query_planning import build_query_plan, ensure_request_query_plan


def test_request_query_plan_is_created_once_and_reused():
    request = DocQARequest(
        prompt="What was revenue in 2023?",
        task_type="numeric",
        verification_domain="finance",
    )

    first = ensure_request_query_plan(request)
    second = ensure_request_query_plan(request)

    assert first is second
    assert request.query_plan is first
    assert request.query_plan_id == first.plan_id


def test_common_from_preposition_does_not_force_cross_page_plan():
    plan = build_query_plan(
        "Who is the chair from the selected paper?",
        answer_type="free_text",
    )

    assert plan.question_type == "simple_fact"


def test_generic_direct_numeric_question_requires_one_operand_not_two():
    plan = build_query_plan(
        "How many participants were included in the study?",
        answer_type="numeric",
    )

    assert [slot.slot_id for slot in plan.evidence_slots] == ["operand:primary"]
    assert plan.evidence_slots[0].required_for_execution is True


def test_metric_phrase_preserves_question_word_order():
    plan = build_query_plan(
        "What was current assets amount?",
        answer_type="numeric",
    )

    assert plan.evidence_slots[0].metric == "current assets"


def test_bound_plan_stage_is_explicit_and_updates_request_state():
    request = DocQARequest(
        prompt="How many participants were included in the study?",
        task_type="numeric",
    )

    bundle = build_evidence_bundle(
        "doc",
        request,
        {
            "evidence": [
                {
                    "evidence_id": "participant-count",
                    "source_id": "paper",
                    "page_label": "3",
                    "text": "The study included 42 participants.",
                }
            ]
        },
    )

    assert bundle.metadata["planned_query_plan"]["stage"] == "planned"
    assert bundle.metadata["bound_query_plan"]["stage"] == "bound"
    assert request.query_plan.as_dict() == bundle.metadata["query_plan"]
    assert request.query_plan.evidence_slots[0].status == "filled"


def test_verified_terminal_slot_states_retain_bound_reference_semantics():
    for status in ("filled", "verified_support", "verified_conflict"):
        slot = EvidenceSlot(
            slot_id="support:proposition",
            role="support",
            status=status,
            evidence_ids=("evidence:paper:authority",),
        )
        assert evidence_slot_references_are_bound(slot)

    assert not evidence_slot_references_are_bound(
        EvidenceSlot(slot_id="support:proposition", role="support")
    )


def test_planner_boolean_plan_receives_static_conjunction_obligation():
    question = "Did the authors evaluate both clinical and legal datasets?"

    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="general",
        planner_payload={
            "plan_id": "planner:unconstrained",
            "answer_type": "boolean",
            "question_type": "simple_fact",
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "role": "support",
                    "statement_kind": "boolean_proposition",
                    "query": question,
                }
            ],
        },
    )

    obligation = plan.constraints["boolean_support_group"]
    assert obligation["operator"] == "all"
    assert obligation["semantics"] == "open_world"
    assert obligation["premise_mode"] == "all_required"
    assert set(obligation["required_argument_tokens"]) == {
        "clinical",
        "dataset",
        "legal",
    }
    assert plan.plan_id != "planner:unconstrained"
