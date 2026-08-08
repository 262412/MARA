from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import bind_evidence_slots
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
    assert restored == 1
    assert "evidence-20" in {item["evidence_id"] for item in selected}


def test_required_slot_shortlist_equal_scores_use_canonical_identity_order():
    plan = _equal_score_plan()
    items = _equal_score_items()

    forward, _ = required_slot_shortlist(items, plan, candidate_limit=2)
    reverse, _ = required_slot_shortlist(list(reversed(items)), plan, candidate_limit=2)

    assert [item["evidence_id"] for item in forward] == ["a", "b"]
    assert [item["evidence_id"] for item in reverse] == ["a", "b"]


def test_query_slot_binding_equal_scores_use_canonical_identity_order():
    plan = _equal_score_plan()
    items = _equal_score_items()

    forward = bind_evidence_slots(plan, items)
    reverse = bind_evidence_slots(plan, list(reversed(items)))

    assert forward.evidence_slots[0].evidence_ids == (
        "evidence:report:a",
        "evidence:report:b",
    )
    assert reverse.evidence_slots[0].evidence_ids == (
        "evidence:report:a",
        "evidence:report:b",
    )


def _equal_score_plan() -> QueryPlan:
    return QueryPlan(
        answer_type="free_text",
        question_type="simple_fact",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:reported",
                role="support",
                metric="reported",
                cardinality=2,
            ),
        ),
    )


def _equal_score_items() -> list[dict[str, str]]:
    return [
        {
            "evidence_id": evidence_id,
            "source_id": "report",
            "text": "Revenue was reported.",
        }
        for evidence_id in ("b", "a")
    ]
