from __future__ import annotations

from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn


def _evidence(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "experiments",
        "text": text,
    }


def test_thorough_strict_policy_is_auditable_through_reverification() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        if request.retrieval_round_id == 1:
            text = "The corpus provides experiments for evaluation."
        else:
            text = "We conduct experiments on the corpus and report the results."
        return {"evidence": [_evidence(f"evidence-{len(calls)}", text)]}

    result = execute_controller_turn(
        DocQARequest(
            prompt="Do the authors conduct experiments on the corpus?",
            retrieval_query="Do the authors conduct experiments on the corpus?",
            task_type="boolean",
            verification_mode="strict",
            verification_domain="qasper",
            route_policy="auto",
            allowed_routes=["doc_text", "hybrid"],
            agent_mode="thorough",
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    assert result.workflow_plan["agent_mode"] == "thorough"
    assert result.workflow_plan["verification_mode"] == "strict"
    assert any(
        step["executor"] == "verify_answer" for step in result.workflow_plan["steps"]
    )

    [workflow_event] = [
        event
        for event in result.controller_trace
        if event.get("stage") == "workflow_plan"
    ]
    assert workflow_event["agent_mode"] == "thorough"
    assert workflow_event["verification_mode"] == "strict"

    recovery_events = [
        event
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt") == 1
    ]
    assert [event["stage"] for event in recovery_events] == [
        "critic",
        "focused_retrieval",
        "evidence_rebind",
        "reverify",
    ]
    assert all(event["agent_mode"] == "thorough" for event in recovery_events)
    assert all(event["verification_mode"] == "strict" for event in recovery_events)
    assert result.verify_decision.mode == "strict"
    assert recovery_events[-1]["verification_status"] == "supported"
    assert recovery_events[-1]["stop_reason"] == "authority_recovered"
