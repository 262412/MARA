from ktem.docqa.evidence_set_objective import marginal_set_gain
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.required_slot_selection import required_slot_shortlist


def test_optional_slot_does_not_consume_required_page_budget():
    plan = QueryPlan(
        answer_type="free_text",
        question_type="simple_fact",
        evidence_slots=(
            EvidenceSlot(
                slot_id="optional",
                role="support",
                metric="optional",
                required=False,
                required_for_retrieval=False,
            ),
            EvidenceSlot(slot_id="required:a", role="support", metric="alpha"),
            EvidenceSlot(slot_id="required:b", role="support", metric="beta"),
            EvidenceSlot(slot_id="required:c", role="support", metric="gamma"),
        ),
    )
    items = [
        {
            "evidence_id": name,
            "source_id": "report",
            "page_label": str(index),
            "text": text,
        }
        for index, (name, text) in enumerate(
            (
                ("optional", "optional context"),
                ("alpha", "alpha evidence"),
                ("beta", "beta evidence"),
                ("gamma", "gamma evidence"),
            ),
            start=1,
        )
    ]

    selected, _trace, bound = select_evidence_for_plan("", items, plan)

    required = [
        slot for slot in bound.evidence_slots if slot.required_for_retrieval
    ]
    assert all(slot.status == "filled" for slot in required)
    assert {item["evidence_id"] for item in selected} >= {"alpha", "beta", "gamma"}


def test_selection_normalizes_incompatible_score_spaces():
    plan = QueryPlan(answer_type="free_text", question_type="simple_fact")
    items = [
        {
            "evidence_id": "irrelevant-element",
            "source_id": "report",
            "text": "Unrelated appendix.",
            "metadata": {"element_retriever_score": 100.0},
        },
        {
            "evidence_id": "relevant-reranked",
            "source_id": "report",
            "text": "Revenue increased.",
            "metadata": {"reranker_score": 0.8},
        },
    ]

    selected, trace, _bound = select_evidence_for_plan("revenue", items, plan)

    assert selected[0]["evidence_id"] == "relevant-reranked"
    assert trace["relevance_score_contract"] == "per_query_rank_normalized_v1"
    assert all("_selection_relevance_score" not in item for item in selected)


def test_marginal_gain_distinguishes_same_page_number_across_sources():
    plan = QueryPlan(answer_type="free_text", question_type="cross_page")
    selected = [
        {
            "evidence_id": "a-page-5",
            "source_id": "document-a",
            "page_label": "5",
            "modality": "text",
        }
    ]
    candidate = {
        "evidence_id": "b-page-5",
        "source_id": "document-b",
        "page_label": "5",
        "modality": "text",
    }

    assert marginal_set_gain(candidate, selected, plan) == 0.2


def test_marginal_structure_gain_accepts_neighbor_alias():
    plan = QueryPlan(answer_type="free_text", question_type="simple_fact")
    selected = [
        {
            "evidence_id": "table-parent",
            "source_id": "report",
            "element_id": "table-1",
        }
    ]
    candidate = {
        "evidence_id": "neighbor",
        "source_id": "report",
        "element_id": "table-2",
        "neighbor_element_ids": ["table-1"],
    }

    assert marginal_set_gain(candidate, selected, plan) == 0.35


def test_required_slot_shortlist_reserves_multiple_candidates_below_global_cutoff():
    plan = QueryPlan(
        answer_type="free_text",
        question_type="cross_page",
        evidence_slots=(
            EvidenceSlot(slot_id="required:alpha", role="support", metric="alpha"),
        ),
    )
    items = [
        {
            "evidence_id": f"global-{index}",
            "source_id": "report",
            "text": "globally relevant distractor",
        }
        for index in range(4)
    ] + [
        {
            "evidence_id": f"alpha-{index}",
            "source_id": "report",
            "text": f"alpha evidence atom {index}",
        }
        for index in range(2)
    ]

    candidates, restored = required_slot_shortlist(
        items,
        plan,
        candidate_limit=4,
    )

    assert {item["evidence_id"] for item in candidates} >= {"alpha-0", "alpha-1"}
    assert restored == 2
