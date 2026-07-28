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
