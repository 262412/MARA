from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def _boolean_page(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    modality: str = "image",
    evidence_level: str = "page",
):
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "page_label": page_label,
        "modality": modality,
        "evidence_level": evidence_level,
        "text": text,
    }


def test_cross_page_plan_requires_distinct_evidence_slots():
    plan = build_query_plan(
        "Compare the result on page 4 with the limitation discussed on page 9.",
        answer_type="free_text",
    )

    assert plan.question_type == "cross_page"
    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "support:left_subject",
        "support:right_subject",
    ]
    assert plan.constraints["requires_distinct_source_pages"] is True

    partial = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "page-4-result",
                "source_id": "paper",
                "page_label": "4",
                "text": "The result on page 4 reports improved accuracy.",
            }
        ],
    )
    complete = bind_evidence_slots(
        plan,
        [
            {
                "evidence_id": "page-4-result",
                "source_id": "paper",
                "page_label": "4",
                "text": "The result on page 4 reports improved accuracy.",
            },
            {
                "evidence_id": "page-9-limitation",
                "source_id": "paper",
                "page_label": "9",
                "text": "The limitation discussed on page 9 is data sparsity.",
            },
        ],
    )

    assert [slot.status for slot in partial.evidence_slots] == [
        "filled",
        "missing",
    ]
    assert all(slot.status == "filled" for slot in complete.evidence_slots)
    assert complete.evidence_slots[0].evidence_ids != (
        complete.evidence_slots[1].evidence_ids
    )


def test_visual_cross_page_question_builds_two_distinct_slots():
    plan = build_query_plan(
        "Compare the table on page 4 with the chart on page 9.",
        answer_type="free_text",
    )

    assert plan.question_type == "cross_page"
    assert plan.constraints["requires_visual"] is True
    assert plan.constraints["requires_multiple_evidence"] is True
    assert plan.constraints["requires_distinct_source_pages"] is True
    assert [slot.modality for slot in plan.evidence_slots] == ["table", "figure"]


def test_common_cross_page_comparison_phrasings_build_distinct_queries():
    questions = (
        "Compare method A and method B.",
        "Method A versus method B.",
        "Give a comparison of method A and method B.",
        "Using pages 4 and 9, explain the difference.",
        "What do pages 4 and 9 jointly show?",
    )

    for question in questions:
        plan = build_query_plan(question, answer_type="free_text")
        queries = [slot.query for slot in plan.evidence_slots]
        assert plan.question_type == "cross_page"
        assert len(queries) == 2
        assert all(query.strip() for query in queries)
        assert queries[0] != queries[1]


def test_boolean_cross_page_plan_separates_locator_and_proposition_authority():
    question = "Across pages 1 and 2, did the authors release the code?"
    page_1 = _boolean_page(
        "page-1",
        "1",
        (
            "Contract Smoke Study - Methods\n"
            "The authors released the code publicly with the paper.\n"
            "The release statement applies to the final evaluated system.\n"
            "Page 1"
        ),
    )
    page_2 = _boolean_page(
        "page-2",
        "2",
        (
            "Contract Smoke Study - Correction\n"
            "The authors did not release the code for the final evaluated system.\n"
            "This correction explicitly supersedes the earlier release statement.\n"
            "Page 2"
        ),
    )

    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    bound = bind_evidence_slots(plan, [page_2, page_1])

    proposition, left, right = bound.evidence_slots
    assert proposition.metric == "authors release code"
    assert proposition.query == question
    assert bound.subqueries == (question, "page 1", "page 2")
    assert left.locator is not None
    assert right.locator is not None
    assert [left.locator.page_label, right.locator.page_label] == ["1", "2"]
    assert left.evidence_ids == (identity_of(page_1).key,)
    assert right.evidence_ids == (identity_of(page_2).key,)
    assert proposition.status == "retrieved_unverified"
    assert proposition.evidence_ids == (
        identity_of(page_1).key,
        identity_of(page_2).key,
    )


def test_cross_page_locator_cleanup_keeps_page_as_a_real_object():
    question = "Across pages 1 and 2, did the authors release page-level annotations?"

    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    assert plan.evidence_slots[0].metric == "authors release page level annotations"


def test_equivalent_explicit_page_locators_are_semantic_only():
    questions = (
        "On pages 4 and 9, did the authors release the code?",
        "Using pages 4 and 9, did the authors release the code?",
        "From page 4 to page 9, did the authors release the code?",
    )

    for question in questions:
        plan = build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        )

        proposition, left, right = plan.evidence_slots
        assert proposition.metric == "authors release code"
        assert proposition.query == question
        assert left.locator is not None
        assert right.locator is not None
        assert [left.locator.page_label, right.locator.page_label] == ["4", "9"]
