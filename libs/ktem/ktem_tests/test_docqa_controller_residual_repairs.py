from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn


def test_ragtruth_task_contract_returns_valid_json_on_empty_retrieval():
    result = execute_controller_turn(
        DocQARequest(
            prompt="Detect unsupported response spans.",
            route_policy="doc",
            verification_mode="off",
            verification_domain="ragtruth",
        ),
        retrieve=lambda *_args: {},
        generate=lambda *_args: "must not run",
    )

    assert result.retrieve_decision.status == "poor"
    assert result.guardrail_decision.action == "return"
    assert result.answer == '{"hallucination list": []}'
    assert result.evidence_bundle.metadata["task_contract_fallback"] == (
        "ragtruth_empty_retrieval"
    )


def test_execute_controller_turn_retries_element_then_falls_back_to_text():
    calls = []

    def retrieve(_request, decision):
        calls.append(decision.legacy_route)
        if decision.legacy_route == "doc_element":
            return {}
        return {
            "evidence": [
                {
                    "evidence_id": "text-1",
                    "file_id": "file-1",
                    "page_label": "3",
                    "text": "The chair is Ada.",
                }
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt="Who is the chair?",
            route_policy="element",
            allowed_routes=["doc_element", "doc_text"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: "The chair is Ada.",
    )

    assert calls == ["doc_element", "doc_element", "doc_text"]
    assert result.controller_decision.legacy_route == "doc_text"
    assert result.controller_trace[0]["failed_retrieval_rounds"] == 2
    assert result.controller_trace[0]["failed_slot_coverage"] is None
