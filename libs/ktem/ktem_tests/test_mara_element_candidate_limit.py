from types import SimpleNamespace

import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import MaraAgentPipeline


def test_mara_element_route_caps_candidates_before_evidence_normalization():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.element_index_records = [
        {
            "evidence_id": f"element:file-b:{index}:text-{index}",
            "file_id": "file-b",
            "file_name": "report.pdf",
            "page_label": str(index),
            "element_id": f"text-{index}",
            "element_type": "text",
            "text": f"Revenue evidence row {index}.",
        }
        for index in range(40)
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "What does the revenue evidence show?",
        [],
        {
            "question": "What does the revenue evidence show?",
            "modalities": ["text"],
        },
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert len(metadata["element_index"]) == 20
    assert metadata["element_candidate_count"] == 40
    assert metadata["element_selected_candidate_count"] == 20


def test_finance_element_limit_restores_each_required_operand_slot():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        page_number=None,
        selected_file_ids=["file-b"],
        active_file_id="file-b",
    )
    distractors = [
        {
            "evidence_id": f"distractor-{index}",
            "file_id": "file-b",
            "page_label": "30",
            "element_id": f"distractor-{index}",
            "element_type": "table",
            "modality": "table",
            "evidence_level": "cell",
            "table_id": "geography-table",
            "cell_id": f"distractor-{index}",
            "row_label": "United States",
            "column_label": "2019",
            "period": "2019",
            "value": str(100 + index),
            "text": (
                "Inventory turnover FY2019 COGS average inventory FY2018 "
                f"FY2019 United States {100 + index}"
            ),
        }
        for index in range(20)
    ]
    required = [
        _finance_cell("cogs-2019", "Cost of products sold", "2019", "15700"),
        _finance_cell("inventory-2019", "Inventories", "2019", "2750"),
        _finance_cell("inventory-2018", "Inventories", "2018", "2500"),
    ]
    pipeline.element_index_records = [*distractors, *required]
    question = (
        "What is FY2019 inventory turnover, defined as FY2019 COGS divided "
        "by average FY2018 and FY2019 inventory?"
    )

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        question,
        [],
        {"question": question, "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    selected_ids = {item["evidence_id"] for item in metadata["element_index"]}
    assert selected_ids >= {item["evidence_id"] for item in required}
    assert metadata["element_required_slot_candidates_restored"] == 3
    assert len(metadata["element_index"]) == 20


def test_element_ranking_uses_active_slot_query(monkeypatch):
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        retrieval_slot_id="operand:net_sales:2019",
        page_number=None,
        selected_file_ids=["file-b"],
        active_file_id="file-b",
    )
    pipeline.element_index_records = [
        {
            **_finance_cell("revenue-2019", "Net sales", "2019", "6489"),
            "statement_kind": "income_statement",
        },
        _finance_cell("ppe-2019", "Property, plant and equipment", "2019", "253"),
    ]
    captured: dict[str, str] = {}
    original_rank = route_retrieval.rank_element_records

    def capture_rank(query, records, **kwargs):
        captured["query"] = query
        return original_rank(query, records, **kwargs)

    monkeypatch.setattr(route_retrieval, "rank_element_records", capture_rank)
    question = (
        "What is FY2019 fixed asset turnover using FY2019 revenue and "
        "average FY2018 and FY2019 property, plant and equipment?"
    )

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "net sales 2019",
        [],
        {"question": question, "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert captured["query"] == "net sales 2019"
    assert metadata["element_active_slot_id"] == "operand:net_sales:2019"
    assert metadata["element_active_slot_candidate_count"] >= 1


def test_active_execution_slot_preserves_matching_parent_table_before_cell_materialization():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        retrieval_slot_id="operand:net_sales:2019",
        page_number=None,
        selected_file_ids=["file-b"],
        active_file_id="file-b",
    )
    distractors = [
        {
            "evidence_id": f"distractor-{index}",
            "file_id": "file-b",
            "page_label": str(index),
            "element_id": f"distractor-{index}",
            "element_type": "table",
            "modality": "table",
            "text": "Net sales 2019 narrative discussion.",
        }
        for index in range(20)
    ]
    parent = {
        "evidence_id": "income-statement-parent",
        "file_id": "file-b",
        "page_label": "44",
        "element_id": "income-statement-parent",
        "element_type": "table",
        "modality": "table",
        "table_id": "income-statement",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "text": (
            "Consolidated Statements of Income\n"
            "2019 2018\n"
            "Net sales 6489 7500\n"
            "Cost of products sold 3900 4200"
        ),
    }
    pipeline.element_index_records = [*distractors, parent]
    question = (
        "What is FY2019 fixed asset turnover using FY2019 revenue and "
        "average FY2018 and FY2019 property, plant and equipment?"
    )

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "net sales 2019",
        [],
        {"question": question, "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert any(
        item["evidence_id"] == "income-statement-parent"
        for item in metadata["element_index"]
    )
    assert metadata["element_active_slot_parent_candidate_count"] == 1


def test_active_execution_slot_prefers_formal_statement_and_keeps_parent_fallback():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(
        answer_type="numeric",
        verification_domain="finance",
        retrieval_slot_id="operand:capital_expenditure:2021",
        page_number=None,
        selected_file_ids=["file-b"],
        active_file_id="file-b",
    )
    distractors = [
        {
            "evidence_id": f"distractor-{index}",
            "file_id": "file-b",
            "page_label": str(index),
            "element_id": f"distractor-{index}",
            "element_type": "table",
            "modality": "table",
            "text": "Capital expenditure 2021 narrative discussion.",
        }
        for index in range(20)
    ]
    free_cash_flow_parent = _cash_flow_parent(
        "free-cash-flow-parent",
        "53",
        "2021 2020 Capital spending (4,625) (4,240)",
    )
    statement_parent = _cash_flow_parent(
        "cash-flow-statement-parent",
        "63",
        (
            "Consolidated Statement of Cash Flows\n"
            "(in millions)\n"
            "2021 2020 2019\n"
            "Capital spending (4,625) (4,240) (4,232)"
        ),
    )
    pipeline.element_index_records = [
        *distractors,
        free_cash_flow_parent,
        statement_parent,
    ]
    question = (
        "What is the FY2021 capital expenditure amount in USD billions "
        "using the consolidated statement of cash flows?"
    )

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "capital expenditure 2021",
        [],
        {"question": question, "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    selected_ids = {item["evidence_id"] for item in metadata["element_index"]}
    assert selected_ids >= {
        "cash-flow-statement-parent",
        "free-cash-flow-parent",
    }
    assert metadata["element_index"][0]["evidence_id"] == ("cash-flow-statement-parent")
    assert metadata["element_active_slot_parent_candidate_count"] == 2


def _cash_flow_parent(evidence_id: str, page_label: str, text: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "file_id": "file-b",
        "page_label": page_label,
        "element_id": evidence_id,
        "element_type": "table",
        "modality": "table",
        "table_id": evidence_id,
        "statement_kind": "cash_flow_statement",
        "financial_scope": "consolidated",
        "text": text,
    }


def _finance_cell(
    evidence_id: str,
    row_label: str,
    period: str,
    value: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "file_id": "file-b",
        "page_label": "52",
        "element_id": "financial-table",
        "element_type": "table",
        "modality": "table",
        "evidence_level": "cell",
        "table_id": "financial-table",
        "cell_id": evidence_id,
        "row_label": row_label,
        "column_label": period,
        "period": period,
        "value": value,
        "statement_kind": (
            "income_statement" if evidence_id.startswith("cogs") else "balance_sheet"
        ),
        "financial_scope": "consolidated",
        "text": f"{row_label} {period} {value}",
    }
