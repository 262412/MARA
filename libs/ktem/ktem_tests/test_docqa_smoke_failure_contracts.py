from __future__ import annotations

from typing import Any

from ktem.docqa.element_parser import parse_element_index_records
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_record_identity import isolate_evidence_records
from ktem.docqa.evidence_set_selection import select_evidence_for_plan
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.financial_table import parse_financial_table_cells
from ktem.docqa.multimodal_index import element_index_documents_from_records
from ktem.docqa.query_planning import build_query_plan


def test_repeated_semantic_financial_rows_have_distinct_physical_cell_identity():
    cells = parse_financial_table_cells(
        {
            "source_id": "report",
            "page_label": "8",
            "evidence_id": "table-parent",
            "element_id": "table-parent",
            "table_id": "table-parent",
            "block_id": "block-1",
            "table_instance_id": "table-instance-1",
            "table_group_id": "balance-sheet",
            "text": (
                "Consolidated balance sheets (in millions)\n"
                "2019 2018\n"
                "Other currencies 10 9\n"
                "Other currencies 12 11"
            ),
        }
    )

    matching = [cell for cell in cells if cell.period == "2019"]
    assert len(matching) == 2
    assert matching[0].cell_id != matching[1].cell_id
    assert matching[0].physical_identity != matching[1].physical_identity
    assert matching[0].semantic_key == matching[1].semantic_key
    assert matching[0].table_instance_id == "table-instance-1"
    assert matching[0].table_group_id == "balance-sheet"
    assert matching[0].block_id == "block-1"
    assert all(str(cell.value) not in cell.cell_id for cell in matching)
    assert all("other-currencies" not in cell.cell_id for cell in matching)


def test_element_ingestion_quarantines_only_conflicting_record():
    records: list[dict[str, Any]] = [
        {
            "evidence_id": "good-1",
            "source_id": "report",
            "page_label": "1",
            "span_id": "span-1",
            "text": "Good evidence one.",
        },
        {
            "evidence_id": "cell-a",
            "source_id": "report",
            "page_label": "2",
            "cell_id": "physical-cell-1",
            "row_index": 1,
            "column_index": 1,
            "value": "10",
            "text": "Revenue 10",
        },
        {
            "evidence_id": "cell-b",
            "source_id": "report",
            "page_label": "2",
            "cell_id": "physical-cell-1",
            "row_index": 2,
            "column_index": 1,
            "value": "12",
            "text": "Revenue 12",
        },
        {
            "evidence_id": "good-2",
            "source_id": "report",
            "page_label": "3",
            "span_id": "span-2",
            "text": "Good evidence two.",
        },
    ]

    result = isolate_evidence_records(records)

    assert [identity_of(item).key for item in result.accepted_records] == [
        "span:report:span-1",
        "cell:report:physical-cell-1",
        "span:report:span-2",
    ]
    assert result.status == "partial"
    assert result.accepted_record_count == 3
    assert result.rejected_record_count == 1
    assert result.identity_conflict_count == 1
    assert result.identity_conflicts[0]["derived_identity"] == (
        "cell:report:physical-cell-1"
    )
    assert set(result.identity_conflicts[0]["conflicting_fields"]) >= {
        "row_index",
        "value",
    }


def test_persisted_element_documents_publish_ingestion_partial_status():
    records = [
        {
            "evidence_id": "cell-a",
            "file_id": "report",
            "file_name": "report.pdf",
            "source_id": "report",
            "page_label": "2",
            "element_id": "table-1",
            "modality": "table",
            "cell_id": "physical-cell-1",
            "row_index": 1,
            "column_index": 1,
            "value": "10",
            "text": "Revenue 10",
            "source_backrefs": ["report#page:2"],
            "metadata": {},
        },
        {
            "evidence_id": "cell-b",
            "file_id": "report",
            "file_name": "report.pdf",
            "source_id": "report",
            "page_label": "2",
            "element_id": "table-1",
            "modality": "table",
            "cell_id": "physical-cell-1",
            "row_index": 2,
            "column_index": 1,
            "value": "12",
            "text": "Revenue 12",
            "source_backrefs": ["report#page:2"],
            "metadata": {},
        },
    ]

    documents = element_index_documents_from_records("report", records)

    assert len(documents) == 1
    trace = documents[0].metadata["element_ingestion_trace"]
    assert trace["element_ingestion_status"] == "partial"
    assert trace["accepted_record_count"] == 1
    assert trace["rejected_record_count"] == 1
    assert trace["identity_conflict_count"] == 1


def test_split_table_blocks_share_group_but_not_physical_instance():
    records = parse_element_index_records(
        doc_id="page-8",
        file_id="report",
        file_name="report.pdf",
        page_label="8",
        text=(
            "Consolidated statements (in millions)\n"
            "2019 2018\nRevenue 10 9\nIncome 3 2\n"
            "Balance sheet (in millions)\n"
            "2019 2018\nAssets 20 18\nInventory 4 3"
        ),
        metadata={},
    )
    tables = [item for item in records if item.get("evidence_level") == "element"]

    assert len(tables) == 2
    assert len({item["table_instance_id"] for item in tables}) == 2
    assert len({item["block_id"] for item in tables}) == 2
    assert {item["table_group_id"] for item in tables} == {"page-8"}
    cell_ids = [
        item["cell_id"] for item in records if item.get("evidence_level") == "cell"
    ]
    assert len(cell_ids) == len(set(cell_ids))


def test_fixed_asset_turnover_plan_has_formula_specific_slots_and_program():
    plan = build_query_plan(
        (
            "What was the fixed asset turnover for 2019 using revenue and "
            "average net PP&E for 2018 and 2019?"
        ),
        answer_type="numeric",
        verification_domain="finance",
    )

    assert [
        (slot.slot_id, slot.metric, slot.period) for slot in plan.evidence_slots
    ] == [
        ("operand:net_sales:2019", "net sales", "2019"),
        (
            "operand:net_property_plant_and_equipment:2018",
            "net property plant and equipment",
            "2018",
        ),
        (
            "operand:net_property_plant_and_equipment:2019",
            "net property plant and equipment",
            "2019",
        ),
    ]
    formula = plan.constraints["finance_formula"]
    assert formula["formula_id"] == "fixed_asset_turnover"
    assert formula["output_unit"] == "ratio"
    assert formula["expression_ast"] == {
        "operator": "divide",
        "inputs": [
            {"ref": "operand:net_sales:2019"},
            {
                "operator": "average",
                "inputs": [
                    {"ref": "operand:net_property_plant_and_equipment:2018"},
                    {"ref": "operand:net_property_plant_and_equipment:2019"},
                ],
            },
        ],
    }


def test_finance_numeric_answer_executes_fixed_asset_turnover_formula():
    answer = finance_numeric_answer(
        (
            "What was fixed asset turnover for 2019 using revenue and average "
            "net PP&E for 2018 and 2019?"
        ),
        [
            {
                "source_id": "report",
                "page_label": "20",
                "element_id": "income-table",
                "text": (
                    "Consolidated statements of income (in millions)\n"
                    "2019 2018\nNet sales 300 280"
                ),
            },
            {
                "source_id": "report",
                "page_label": "21",
                "element_id": "balance-table",
                "text": (
                    "Consolidated balance sheets (in millions)\n"
                    "2019 2018\nProperty, plant and equipment, net 120 80"
                ),
            },
        ],
    )

    assert answer is not None
    assert answer.answer == "3"
    assert answer.question_type == "fixed_asset_turnover"
    assert answer.calculation_verification["valid"] is True
    assert [step["operator"] for step in answer.calculation_plan["steps"]] == [
        "average",
        "ratio",
    ]


def test_qasper_runtime_task_type_selects_boolean_or_free_text():
    boolean_plan = build_query_plan(
        "Do the authors conduct experiments on the tasks mentioned?",
        answer_type="qasper_qa",
        verification_domain="qasper",
    )
    free_text_plan = build_query_plan(
        "What background knowledge do they leverage?",
        answer_type="qasper_qa",
        verification_domain="qasper",
    )

    assert boolean_plan.answer_type == "boolean"
    assert boolean_plan.question_type == "simple_fact"
    assert [slot.slot_id for slot in boolean_plan.evidence_slots] == [
        "support:boolean_proposition"
    ]
    assert free_text_plan.answer_type == "free_text"


def test_boolean_required_slot_reserves_best_proposition_evidence():
    question = "Did the authors release the code?"
    plan = build_query_plan(
        question,
        answer_type="qasper_qa",
        verification_domain="qasper",
    )
    distractors = [
        {
            "evidence_id": f"distractor-{index}",
            "source_id": "paper",
            "page_label": str(index),
            "text": "The paper reports evaluation results and model accuracy.",
            "score": 1.0 - index / 100,
        }
        for index in range(1, 12)
    ]
    target = {
        "evidence_id": "release-evidence",
        "source_id": "paper",
        "page_label": "20",
        "text": "The authors released the code publicly with the paper.",
        "score": 0.01,
    }

    selected, trace, bound = select_evidence_for_plan(
        question,
        [*distractors, target],
        plan,
    )

    assert "release-evidence" in {item["evidence_id"] for item in selected}
    assert bound.evidence_slots[0].status == "filled"
    assert trace["required_slot_bindings"][0]["slot_id"] == (
        "support:boolean_proposition"
    )
    assert trace["required_slot_bindings"][0]["selected_evidence_ids"]
