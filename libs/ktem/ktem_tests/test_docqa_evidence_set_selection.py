from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.query_planning import build_query_plan


def test_selection_keeps_similar_evidence_when_each_fills_required_period_slot():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    items = [
        _item("revenue-2021", "4", "Revenue was $10 million in 2021.", 0.9),
        _item("revenue-2022", "5", "Revenue was $12 million in 2022.", 0.89),
        _item("distractor", "20", "The company described its strategy.", 0.95),
    ]

    selected, trace, bound = select_evidence_for_plan(
        "percentage change revenue 2021 2022",
        items,
        plan,
    )

    assert {item["evidence_id"] for item in selected} >= {
        "revenue-2021",
        "revenue-2022",
    }
    assert trace["slot_coverage"] == 1.0
    assert not [slot for slot in bound.evidence_slots if slot.status == "missing"]


def test_selection_expands_table_continuation_and_respects_page_budget():
    plan = build_query_plan(
        "Compare the revenue table across the report pages.",
        answer_type="free_text",
    )
    items = [
        {
            **_item("table-p4", "4", "Revenue table, first half.", 0.95),
            "continuation_id": "revenue-table",
            "table_id": "table-7",
        },
        {
            **_item("table-p5", "5", "Revenue table, continued.", 0.7),
            "continuation_id": "revenue-table",
            "table_id": "table-7",
        },
    ] + [
        {
            **_item(f"noise-{page}", str(page), "Unrelated appendix.", 0.6),
            "section_id": "appendix",
        }
        for page in range(10, 20)
    ]

    selected, trace, _bound = select_evidence_for_plan(
        "compare revenue table",
        items,
        plan,
    )

    assert {"table-p4", "table-p5"} <= {item["evidence_id"] for item in selected}
    assert trace["continuation_expansion_count"] == 1
    assert trace["structure_expansion_enabled"] is True
    assert trace["unique_pages"] <= trace["max_pages"]


def test_selection_disables_structure_expansion_for_legacy_low_coverage_index():
    plan = build_query_plan(
        "Compare revenue across the report pages.",
        answer_type="free_text",
    )
    items = [
        {
            **_item("table-p4", "4", "Revenue first half.", 0.95),
            "continuation_id": "revenue-table",
        },
        {
            **_item("table-p5", "5", "Revenue continued.", 0.1),
            "continuation_id": "revenue-table",
        },
        *[
            _item(f"legacy-{index}", str(index + 10), "Legacy chunk.", 0.8)
            for index in range(8)
        ],
    ]

    _selected, trace, _bound = select_evidence_for_plan(
        "compare revenue",
        items,
        plan,
    )

    assert trace["structure_metadata_coverage"] == 0.2
    assert trace["structure_expansion_enabled"] is False
    assert trace["continuation_expansion_count"] == 0


def _item(evidence_id, page, text, score):
    return {
        "evidence_id": evidence_id,
        "canonical_id": f"evidence:{evidence_id}",
        "source_id": "report",
        "page_label": page,
        "text": text,
        "modality": "text",
        "metadata": {"hybrid_fusion_score": score},
    }
