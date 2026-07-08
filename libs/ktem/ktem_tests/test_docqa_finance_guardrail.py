from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


def test_finance_benchmark_unsupported_answer_returns_revise_not_abstain():
    def retrieve(_request, _decision):
        return _quick_ratio_evidence_metadata()

    def generate(_request, _decision, _bundle):
        return (
            "Based on current assets, inventories, and current liabilities, "
            "3M's quick ratio was 1.20."
        )

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

    assert result.verify_decision.status == "unsupported"
    assert result.guardrail_decision.action == "revise"
    assert result.answer != ABSTAIN_MESSAGE
    assert "quick ratio was 1.20" in result.answer


def test_finance_benchmark_source_level_evidence_reaches_generator():
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
        return "The quick ratio cannot be calculated from the available fields."

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

    assert result.retrieve_decision.status == "good"
    assert result.guardrail_decision.action == "return"
    assert result.answer == (
        "The quick ratio cannot be calculated from the available fields."
    )


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
