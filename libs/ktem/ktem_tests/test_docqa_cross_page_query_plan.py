from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


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
