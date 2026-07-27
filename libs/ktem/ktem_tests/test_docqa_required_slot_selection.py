from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.required_slot_selection import required_slot_shortlist


def test_required_slot_shortlist_never_expands_fixed_candidate_budget():
    slots = tuple(
        EvidenceSlot(
            slot_id=f"slot-{index}",
            role="support",
            metric=f"metric{index}",
        )
        for index in range(21)
    )
    items = [
        {
            "evidence_id": f"evidence-{index}",
            "text": f"metric{index}",
        }
        for index in range(21)
    ]
    plan = QueryPlan(
        answer_type="free_text",
        question_type="simple_fact",
        evidence_slots=slots,
    )

    selected, restored = required_slot_shortlist(
        items,
        plan,
        candidate_limit=20,
    )

    assert len(selected) == 20
    assert restored == 0
