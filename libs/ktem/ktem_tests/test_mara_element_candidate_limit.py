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
