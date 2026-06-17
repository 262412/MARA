from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn


def test_execute_controller_turn_switches_route_after_ambiguous_finance_retrieval():
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

    assert calls == ["hybrid", "hybrid", "doc_text"]
    assert result.controller_decision.legacy_route == "doc_text"
    assert result.retrieve_decision.status == "good"
    assert result.controller_trace[0]["stage"] == "route_switch"
    assert result.controller_trace[0]["from_route"] == "hybrid"
    assert result.controller_trace[0]["to_route"] == "doc_text"
