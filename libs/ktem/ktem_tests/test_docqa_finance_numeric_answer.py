from types import SimpleNamespace

from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.reasoning.mara_finance_answering import route_finance_numeric_answer


def test_finance_numeric_answer_computes_quick_ratio_from_evidence_text():
    answer = finance_numeric_answer(
        "What was 3M's quick ratio in 2022?",
        [
            {
                "evidence_id": "balance-sheet-cell",
                "text": (
                    "Current assets were $14,688 million, inventories were "
                    "$4,962 million, and current liabilities were $10,116 million."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "0.96"
    assert answer.confidence >= 0.7
    assert answer.question_type == "quick_ratio"
    assert answer.calculation_plan["contract_id"] == "calculation_plan.v1"
    assert answer.calculation_verification["valid"] is True
    assert answer.calculation_execution["citation_ids"] == ["balance-sheet-cell"]


def test_finance_numeric_answer_computes_percentage_change():
    answer = finance_numeric_answer(
        "What was the percentage change in revenue from 2021 to 2022?",
        [
            {
                "evidence_id": "revenue-table-cells",
                "text": (
                    "Revenue was $10.0 million in 2021. Revenue was "
                    "$12.5 million in 2022."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "25.0%"
    assert answer.question_type == "percentage_change"


def test_finance_numeric_answer_parses_negative_parentheses_for_difference():
    answer = finance_numeric_answer(
        "What was the difference in operating income from 2021 to 2022?",
        [
            {
                "evidence_id": "operating-income-cells",
                "text": (
                    "Operating income was $(120) million in 2021. "
                    "Operating income was $80 million in 2022."
                ),
            }
        ],
    )

    assert answer is not None
    assert answer.answer == "$200.0 million"
    assert answer.inputs["prior"] == -120.0


def test_finance_numeric_answer_does_not_emit_untraceable_guess():
    answer = finance_numeric_answer(
        "What was the percentage change in revenue from 2021 to 2022?",
        [{"text": "Revenue was 10 in 2021. Revenue was 12 in 2022."}],
    )

    assert answer is not None
    assert answer.answer == ""
    assert answer.confidence == 0.0
    assert not answer.calculation_verification["valid"]


def test_finance_route_blocks_llm_fallback_after_calculation_verification_failure():
    bundle = SimpleNamespace(
        items=[{"text": "Revenue was 10 in 2021. Revenue was 12 in 2022."}],
        metadata={},
    )

    answer = route_finance_numeric_answer(
        SimpleNamespace(
            prompt="What was the percentage change in revenue from 2021 to 2022?",
            verification_domain="finance",
        ),
        SimpleNamespace(route="hybrid_rag"),
        bundle,
    )

    assert answer == ""
    assert bundle.metadata["generation_backend"] == (
        "finance_calculation_verification_failed"
    )
    assert not bundle.metadata["finance_numeric_trace"]["calculation_verification"][
        "valid"
    ]
