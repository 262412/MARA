from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn


def test_route_switch_trace_preserves_failed_attempt_before_committed_transition():
    calls: list[str] = []

    def retrieve(_request, decision):
        calls.append(decision.legacy_route)
        if decision.legacy_route != "graph_global":
            return {}
        return {
            "graph_evidence": [
                {
                    "id": "graph-answer",
                    "label": "Graph answer",
                    "summary": "The graph evidence answers the question.",
                    "source_ids": ["paper"],
                }
            ]
        }

    result = execute_controller_turn(
        DocQARequest(
            prompt="What does the document say?",
            route_policy="doc",
            allowed_routes=["doc_text", "hybrid", "graph_global"],
        ),
        retrieve=retrieve,
        generate=lambda *_args: "The graph evidence answers the question.",
    )

    assert calls == ["doc_text", "hybrid", "graph_global"]
    attempts = [
        event
        for event in result.controller_trace
        if event.get("stage") in {"route_switch_attempt", "route_switch"}
    ]
    assert [event["stage"] for event in attempts] == [
        "route_switch_attempt",
        "route_switch",
    ]
    failed, committed = attempts
    assert failed["from_route"] == "doc_text"
    assert failed["to_route"] == "hybrid"
    assert failed["attempt"] == 1
    assert failed["attempt_status"] == "ambiguous"
    assert failed["transition_committed"] is False
    assert failed["route_switch_used"] is False
    assert committed["to_route"] == "graph_global"
    assert committed["attempt"] == 2
    assert committed["attempt_status"] == "good"
    assert committed["transition_committed"] is True
