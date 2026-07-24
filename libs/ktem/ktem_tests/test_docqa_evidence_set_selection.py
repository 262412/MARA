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


def test_selection_prefers_complete_question_phrase_anchors_for_simple_fact():
    query = 'Who sings a version of "I\'ll Be Seeing You" in The Notebook?'
    plan = build_query_plan(
        query,
        answer_type="citation_qa",
        verification_domain="alce",
    )
    items = [
        _item(
            "song-only",
            "1",
            'The song "I\'ll Be Seeing You" has been recorded by many artists.',
            0.9,
        ),
        _item(
            "notebook-answer",
            "2",
            "In The Notebook, a version of I'll Be Seeing You is sung by "
            "Billie Holiday.",
            0.05,
        ),
    ]

    selected, _trace, _bound = select_evidence_for_plan(query, items, plan)

    assert selected[0]["evidence_id"] == "notebook-answer"


def test_selection_reads_runtime_reranking_score_field():
    query = "When did the Bellagio in Las Vegas open?"
    plan = build_query_plan(
        query,
        answer_type="citation_qa",
        verification_domain="alce",
    )
    low_score = _item(
        "low-score",
        "1",
        "The Bellagio in Las Vegas opened on October 15, 1998.",
        0.0,
    )
    high_score = _item(
        "high-score",
        "2",
        "The Bellagio in Las Vegas opened on October 15, 1998.",
        0.0,
    )
    low_score["metadata"] = {"reranking_score": 0.1}
    high_score["metadata"] = {"reranking_score": 0.9}

    selected, _trace, _bound = select_evidence_for_plan(
        query,
        [low_score, high_score],
        plan,
    )

    assert selected[0]["evidence_id"] == "high-score"


def test_selection_prefers_evidence_matching_both_date_boundaries():
    query = (
        "Who was the US Speaker for the House of Representatives from "
        "January 6, 2015 to October 29, 2015?"
    )
    plan = build_query_plan(
        query,
        answer_type="citation_qa",
        verification_domain="alce",
    )
    items = [
        _item(
            "partial-date",
            "1",
            "Paul Ryan was Speaker after October 29, 2015.",
            0.95,
        ),
        _item(
            "complete-range",
            "2",
            "From January 6, 2015 to October 29, 2015, John Boehner was "
            "Speaker of the US House.",
            0.2,
        ),
    ]

    selected, _trace, _bound = select_evidence_for_plan(query, items, plan)

    assert selected[0]["evidence_id"] == "complete-range"


def test_selection_preserves_lowercase_multiword_entity_anchors():
    query = "What episode does jason gideon die in criminal minds as flashback?"
    plan = build_query_plan(
        query,
        answer_type="citation_qa",
        verification_domain="alce",
    )
    items = [
        _item(
            "series-distractor",
            "1",
            "An episode of Criminal Minds explains another character's death.",
            0.9,
        ),
        _item(
            "gideon-answer",
            "2",
            'In Criminal Minds episode "Nelson\'s Sparrow," Jason Gideon was '
            "murdered off-screen.",
            0.05,
        ),
    ]

    selected, _trace, _bound = select_evidence_for_plan(query, items, plan)

    assert selected[0]["evidence_id"] == "gideon-answer"


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
