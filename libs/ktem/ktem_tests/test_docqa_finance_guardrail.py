from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


def test_finance_benchmark_page_only_operands_abstain_before_generation():
    def retrieve(_request, _decision):
        return _quick_ratio_evidence_metadata()

    def generate(_request, _decision, _bundle):
        raise AssertionError("page-only finance operands must not reach generation")

    result = execute_controller_turn(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            route_policy="doc",
            verification_mode="strict",
            verification_domain="finance",
            origin="benchmark",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.verify_decision.status == "not_enough_evidence"
    assert result.guardrail_decision.action == "abstain"
    assert result.answer == ABSTAIN_MESSAGE


def test_finance_benchmark_source_level_evidence_does_not_fill_atomic_slots():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "source-level-hit",
                    "file_id": "file-1",
                    "text": (
                        "Total current assets were $15,754 million. "
                        "Liquidity was discussed in the annual report."
                    ),
                }
            ]
        }

    def generate(_request, _decision, _bundle):
        raise AssertionError(
            "source-level finance evidence must not fill atomic operand slots"
        )

    result = execute_controller_turn(
        DocQARequest(
            prompt=_quick_ratio_prompt(),
            route_policy="doc",
            verification_mode="light",
            verification_domain="finance",
            origin="benchmark",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"
    assert result.answer == ABSTAIN_MESSAGE


def _quick_ratio_prompt() -> str:
    return (
        "Does 3M have a reasonably healthy liquidity profile based on its quick "
        "ratio for Q2 of FY2023?"
    )


def _quick_ratio_evidence_metadata() -> dict:
    return {
        "evidence": [
            {
                "evidence_id": "balance-sheet-page",
                "file_id": "file-1",
                "page_label": "4",
                "text": (
                    "Total current assets $15,754 million. "
                    "Total inventories $5,280 million. "
                    "Total current liabilities $10,936 million."
                ),
            }
        ]
    }
