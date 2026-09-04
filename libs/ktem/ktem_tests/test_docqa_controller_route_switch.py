from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn


def test_route_switch_does_not_accept_non_atomic_finance_page_as_recovery():
    calls = []

    def retrieve(_request, decision):
        calls.append(decision.legacy_route)
        if decision.legacy_route == "hybrid":
            return {
                "evidence": [
                    {
                        "evidence_id": "derivative-page",
                        "file_id": "aes-2022",
                        "page_label": "152",
                        "text": "Derivative credit ratings and counterparty exposure.",
                    }
                ]
            }
        return {
            "evidence": [
                {
                    "evidence_id": "statement-page",
                    "file_id": "aes-2022",
                    "page_label": "132",
                    "text": (
                        "Consolidated Statements of Operations. Cost of sales "
                        "$10,230. Consolidated Balance Sheets. Inventories $1,077."
                    ),
                }
            ]
        }

    def generate(_request, decision, bundle):
        assert decision.legacy_route == "doc_text"
        assert bundle.items[0]["evidence_id"] == "statement-page"
        return "AES converted inventory about 9.5 times in FY2022."

    result = execute_controller_turn(
        DocQARequest(
            prompt="Calculate AES Corporation inventory turnover ratio for FY2022.",
            route_policy="hybrid",
            allowed_routes=["hybrid", "doc_text"],
            verification_domain="finance",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert calls == [
        "hybrid",
        "hybrid",
        "hybrid",
        "hybrid",
        "doc_text",
        "doc_text",
    ]
    assert result.controller_decision.legacy_route == "hybrid"
    assert result.controller_decision.route_switch_used is False
    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "abstain"
    assert all(event["stage"] != "route_switch" for event in result.controller_trace)
