from ktem.docqa.controller import RouteDecision
from ktem.docqa.route_selection import controller_decision_from_route


def test_controller_decision_preserves_required_hybrid_eligibility():
    decision = controller_decision_from_route(
        RouteDecision(
            route="hybrid",
            policy="cost_aware",
            controller_mode="llm",
            requires_retrieval=True,
            reason="Structured calculation requires complementary evidence.",
        ),
        canonical_routes={"hybrid": "hybrid_rag"},
        planner_payload={
            "route_selection_policy": "cost_aware_initial",
            "planner_route": "hybrid",
            "cost_gate_decision": "required_evidence_preserved",
            "required_evidence_route_available": True,
            "routing_features": {"structured_calculation": True},
        },
    )

    assert decision.required_evidence_route_available is True
    assert decision.as_dict()["required_evidence_route_available"] is True
