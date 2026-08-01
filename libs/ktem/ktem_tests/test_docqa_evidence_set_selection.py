from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.query_plan_schema import EvidenceLocator, EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan


def test_selection_keeps_similar_evidence_when_each_fills_required_period_slot():
    plan = build_query_plan(
        "What was the percentage change in revenue from 2021 to 2022?",
        answer_type="numeric",
        verification_domain="finance",
    )
    items = [
        _cell_item(
            "revenue-2021",
            "4",
            "Revenue was $10 million in 2021.",
            0.9,
            row_label="Revenue",
            period="2021",
            value="10",
        ),
        _cell_item(
            "revenue-2022",
            "5",
            "Revenue was $12 million in 2022.",
            0.89,
            row_label="Revenue",
            period="2022",
            value="12",
        ),
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


def test_selection_restores_required_slot_evidence_below_rerank_cutoff():
    plan = build_query_plan(
        "What were total current assets in FY2021?",
        answer_type="numeric",
        verification_domain="finance",
    )
    distractors = [
        _item(
            f"distractor-{index}",
            str(index + 1),
            f"General financial discussion {index}.",
            1.0 - index / 100,
        )
        for index in range(30)
    ]
    required = _cell_item(
        "current-assets-2021",
        "31",
        "Total current assets were $19,815 million in 2021.",
        0.1,
        row_label="Total current assets",
        period="2021",
        value="19815",
    )

    selected, trace, bound = select_evidence_for_plan(
        "total current assets 2021",
        [*distractors, required],
        plan,
    )

    assert "current-assets-2021" in {item["evidence_id"] for item in selected}
    assert trace["required_slot_candidates_restored"] == 1
    assert trace["slot_coverage"] == 1.0
    assert all(slot.status == "filled" for slot in bound.evidence_slots)


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
    assert trace["continuation_expansion_count"] == 0
    assert trace["structure_expansion_enabled"] is True
    assert trace["unique_pages"] <= trace["max_pages"]


def test_selection_expands_available_structure_edges_in_mixed_legacy_index():
    plan = build_query_plan(
        "Explain revenue in the report.",
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
        "explain revenue",
        items,
        plan,
    )

    assert trace["structure_metadata_coverage"] == 0.2
    assert trace["structure_expansion_enabled"] is True
    assert trace["continuation_expansion_count"] == 1


def test_neighbor_alias_expansion_uses_canonical_identity():
    plan = build_query_plan(
        "What was revenue?",
        answer_type="free_text",
    )
    items = [
        {
            **_item("revenue-table", "4", "Revenue was 42 million.", 0.9),
            "element_id": "table-a",
            "neighbor_element_ids": ["table-b"],
        },
        {
            **_item("table-note", "5", "Units are in millions.", 0.1),
            "element_id": "table-b",
        },
    ]

    selected, trace, _bound = select_evidence_for_plan(
        "What was revenue?",
        items,
        plan,
    )

    assert {item["element_id"] for item in selected} == {"table-a", "table-b"}
    assert trace["continuation_expansion_count"] == 1


def test_finance_structure_coverage_uses_element_index_not_mixed_page_pool():
    plan = build_query_plan(
        "What were total current assets in FY2021?",
        answer_type="numeric",
        verification_domain="finance",
    )
    cell = _cell_item(
        "current-assets-2021",
        "4",
        "Total current assets were 19,815 million in 2021.",
        0.6,
        row_label="Total current assets",
        period="2021",
        value="19815",
    )
    items = [
        cell,
        *[
            _item(f"page-{index}", str(index + 10), "Legacy page chunk.", 0.9)
            for index in range(4)
        ],
    ]

    _selected, trace, _bound = select_evidence_for_plan(
        "total current assets 2021",
        items,
        plan,
    )

    assert trace["mixed_candidate_structure_metadata_coverage"] == 0.2
    assert trace["structure_metadata_coverage"] == 1.0
    assert trace["structure_coverage_scope"] == "element_index"
    assert trace["structure_expansion_enabled"] is False


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


def test_atomic_reservations_preserve_required_factual_evidence() -> None:
    plan = QueryPlan(
        answer_type="numeric",
        question_type="numeric",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:outlook",
                role="support",
                metric="supply disruption",
            ),
            EvidenceSlot(
                slot_id="operand:current_assets:2021",
                role="operand",
                metric="current_assets",
                period="2021",
                statement_kind="balance_sheet",
                financial_scope="consolidated",
                required_for_execution=True,
            ),
        ),
        constraints={"requires_structure": True},
    )
    factual = _item(
        "outlook",
        "9",
        "Management expects the supply disruption to ease next year.",
        0.01,
    )
    operand = _cell_item(
        "assets",
        "12",
        "Consolidated current assets in 2021 were 120 million.",
        0.02,
        row_label="Current assets",
        period="2021",
        value="120",
    )
    operand["statement_kind"] = "balance_sheet"
    operand["financial_scope"] = "consolidated"
    calculation_noise = [
        {
            **operand,
            "evidence_id": f"noise-{index}",
            "canonical_id": f"evidence:noise-{index}",
            "cell_id": f"noise-{index}",
            "value": str(index + 1),
            "metadata": {"reranking_score": 1.0 - index / 100},
        }
        for index in range(20)
    ]

    selected, trace, bound = select_evidence_for_plan(
        "Explain supply disruption and report current assets in 2021",
        [*calculation_noise, operand, factual],
        plan,
    )

    assert "outlook" in {item["evidence_id"] for item in selected}
    assert all(slot.status == "filled" for slot in bound.evidence_slots)
    assert trace["selected_budget_usage"]["factual_narrative"] >= 1
    assert trace["selected_budget_usage"]["execution_operands"] >= 1


def test_reranker_cannot_override_incompatible_metric_or_period() -> None:
    plan = build_query_plan(
        "What were current assets in FY2021?",
        answer_type="numeric",
        verification_domain="finance",
    )
    wrong = _cell_item(
        "wrong",
        "12",
        "Current liabilities in 2020 were 999 million.",
        1.0,
        row_label="Current liabilities",
        period="2020",
        value="999",
    )
    correct = _cell_item(
        "correct",
        "13",
        "Current assets in 2021 were 120 million.",
        0.01,
        row_label="Current assets",
        period="2021",
        value="120",
    )

    selected, trace, bound = select_evidence_for_plan(
        "current assets 2021",
        [wrong, correct],
        plan,
    )

    [operand] = [slot for slot in bound.evidence_slots if slot.role == "operand"]
    assert operand.evidence_ids == ("cell:report:correct",)
    [binding] = trace["required_slot_bindings"]
    reasons = {
        item["evidence_id"]: item["reason"]
        for item in binding["candidate_drop_reasons"]
    }
    assert reasons["cell:report:wrong"] == "semantic_slot_mismatch"
    assert "correct" in {item["evidence_id"] for item in selected}


def test_required_gold_page_remains_selected_with_active_locator() -> None:
    plan = QueryPlan(
        answer_type="free_text",
        question_type="simple_fact",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:gold-page",
                role="support",
                metric="reported outlook",
                locator=EvidenceLocator(source_id="report", page_label="9"),
            ),
        ),
    )
    wrong_page = _item(
        "wrong-page",
        "2",
        "The reported outlook was positive.",
        1.0,
    )
    gold_page = _item(
        "gold-page",
        "9",
        "The reported outlook was cautious.",
        0.01,
    )

    selected, _trace, bound = select_evidence_for_plan(
        "reported outlook",
        [wrong_page, gold_page],
        plan,
    )

    assert "gold-page" in {item["evidence_id"] for item in selected}
    assert bound.evidence_slots[0].evidence_ids == ("evidence:report:gold-page",)


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


def _cell_item(
    evidence_id,
    page,
    text,
    score,
    *,
    row_label,
    period,
    value,
):
    return {
        **_item(evidence_id, page, text, score),
        "modality": "table",
        "evidence_level": "cell",
        "element_id": f"table-{page}",
        "table_id": f"table-{page}",
        "cell_id": evidence_id,
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "value": value,
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
    }
