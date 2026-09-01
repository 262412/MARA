import pytest
from ktem.docqa.query_planning import build_query_plan


@pytest.mark.parametrize(
    ("question", "answer_type", "expected_slot_id"),
    (
        (
            "Did the authors test whether the model linked image regions to "
            "entity labels?",
            "qa",
            "support:boolean_proposition",
        ),
        (
            "Do they inspect their model to see if their model learned to "
            "associate image parts with words related to entities?",
            "qa",
            "support:boolean_proposition",
        ),
        (
            "Did the figure experiment improve entity recognition?",
            "qa",
            "support:boolean_proposition",
        ),
        (
            "How does the paper describe the visual feature ablation experiment?",
            "free_text",
            "support:answer_relation",
        ),
    ),
)
def test_textual_visual_discussion_keeps_semantic_authority(
    question: str,
    answer_type: str,
    expected_slot_id: str,
) -> None:
    plan = build_query_plan(
        question,
        answer_type=answer_type,
        verification_domain="qasper",
    )

    assert plan.constraints["requires_visual"] is False
    assert all(slot.slot_id != "support:visual_primary" for slot in plan.evidence_slots)
    assert [slot.slot_id for slot in plan.evidence_slots] == [expected_slot_id]
    assert plan.evidence_slots[0].modality == "auto"


@pytest.mark.parametrize(
    ("question", "expected_modality"),
    (
        ("What does Figure 3 show?", "figure"),
        ("According to Figure 3, which method performs best?", "figure"),
        ("Which label is shown on the slide?", "page_image"),
        ("What value is in the table?", "table"),
        ("Which objects are visible in the image?", "page_image"),
        ("Describe the image.", "page_image"),
    ),
)
def test_visual_content_questions_require_visual_primary(
    question: str,
    expected_modality: str,
) -> None:
    plan = build_query_plan(question, answer_type="free_text")

    assert plan.constraints["requires_visual"] is True
    assert plan.question_type == "visual"
    assert [slot.slot_id for slot in plan.evidence_slots] == ["support:visual_primary"]
    assert plan.evidence_slots[0].modality == expected_modality
