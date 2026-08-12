from benchmark.verifier_observability import (
    prediction_verifier_observability,
    route_verifier_observability_table,
    verifier_observability_summary,
)


def test_prediction_verifier_observability_counts_abstention_claims_and_control():
    prediction = {
        "predicted_answer": "Insufficient evidence to answer.",
        "gold_answers": ["Revenue rose"],
        "metrics": {
            "abstained": 1.0,
            "false_abstention": 1.0,
            "unsupported_claim_count": 2.0,
        },
        "verify_decision": {
            "status": "unsupported",
            "unsupported_claims": ["Unsupported A", "Unsupported B"],
        },
        "claim_verification": {"unsupported_claims": ["Unsupported C"]},
        "controller_trace": [
            {"stage": "retrieve", "action": "retry", "retry": True},
            {
                "stage": "route_switch",
                "from_route": "doc_text",
                "to_route": "hybrid",
            },
        ],
        "agent_trace": [{"event": "retry_generation"}],
        "workflow_plan": {
            "steps": [
                {"action": "switch_route", "from_route": "hybrid", "to_route": "graph"}
            ]
        },
    }

    observability = prediction_verifier_observability(prediction)

    assert observability == {
        "abstained": 1,
        "true_abstention": 0,
        "false_abstention": 1,
        "unsupported_claim_count": 3,
        "has_unsupported_claim": 1,
        "retry_count": 2,
        "route_switch_count": 2,
    }


def test_prediction_verifier_observability_deduplicates_repeated_route_transition():
    transition = {
        "stage": "route_switch",
        "from_route": "doc_text",
        "to_route": "hybrid",
    }
    prediction = {
        "controller_trace": [dict(transition)],
        "agent_trace": [dict(transition, stage="agent_route_switch")],
        "workflow_plan": {
            "steps": [dict(transition, stage="workflow_route_switch")],
            "events": [dict(transition, stage="planner_route_switch")],
        },
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["route_switch_count"] == 1


def test_route_switch_summary_marker_is_not_a_second_transition():
    transition = {
        "stage": "route_switch",
        "from_route": "doc_text",
        "to_route": "hybrid",
        "route_switch_used": True,
    }
    planner_summary = {
        "stage": "planner",
        "legacy_route": "hybrid",
        "initial_route": "doc_text",
        "final_route": "hybrid",
        "route_switch_used": True,
        "route_switch_candidates": ["hybrid"],
        "override_reason": "Route switch used only after retrieval failure.",
    }
    prediction = {
        "controller_trace": [transition, planner_summary],
        "agent_trace": [dict(transition, event="route_switch")],
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["route_switch_count"] == 1


def test_prediction_verifier_observability_preserves_distinct_routes_and_retries():
    route_one = {
        "logical_transition_key": "route-switch-1",
        "from_route": "doc_text",
        "to_route": "hybrid",
    }
    route_two = {
        "event_id": "route-switch-2",
        "from_route": "hybrid",
        "to_route": "graph",
    }
    retry_one = {
        "retry": True,
        "attempt": 1,
        "action": "retrieval_retry",
    }
    retry_two = {
        "retry": True,
        "attempt": 2,
        "action": "retrieval_retry",
    }
    prediction = {
        "controller_trace": [route_one, retry_one],
        "agent_trace": [route_two, retry_two],
        "workflow_plan": {
            "events": [
                dict(route_one, stage="workflow"),
                dict(route_two, stage="workflow"),
                dict(retry_one, stage="workflow"),
                dict(retry_two, stage="workflow"),
            ]
        },
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["route_switch_count"] == 2
    assert observability["retry_count"] == 2


def test_verifier_observability_summary_and_route_table_counts_predictions():
    predictions = [
        {
            "route": "crag_guarded",
            "verifier_observability": {
                "abstained": 1,
                "true_abstention": 1,
                "false_abstention": 0,
                "unsupported_claim_count": 1,
                "has_unsupported_claim": 1,
                "retry_count": 1,
                "route_switch_count": 0,
            },
        },
        {
            "route": "crag_guarded",
            "verifier_observability": {
                "abstained": 1,
                "true_abstention": 0,
                "false_abstention": 1,
                "unsupported_claim_count": 0,
                "has_unsupported_claim": 0,
                "retry_count": 2,
                "route_switch_count": 1,
            },
        },
    ]

    assert verifier_observability_summary(predictions) == {
        "num_abstention": 2,
        "num_true_abstention": 1,
        "num_false_abstention": 1,
        "num_unsupported_claim": 1,
        "total_unsupported_claim_count": 1,
        "num_retry": 2,
        "total_retry_count": 3,
        "num_route_switch": 1,
        "total_route_switch_count": 1,
        "true_abstention_rate": 0.5,
        "false_abstention_rate": 0.5,
        "unsupported_claim_rate": 0.5,
        "retry_rate": 1.0,
        "route_switch_rate": 0.5,
    }
    assert route_verifier_observability_table("qasper", predictions) == [
        {
            "dataset_name": "qasper",
            "route": "crag_guarded",
            "num_predictions": 2,
            "num_abstention": 2,
            "num_true_abstention": 1,
            "num_false_abstention": 1,
            "num_unsupported_claim": 1,
            "total_unsupported_claim_count": 1,
            "num_retry": 2,
            "total_retry_count": 3,
            "num_route_switch": 1,
            "total_route_switch_count": 1,
            "true_abstention_rate": 0.5,
            "false_abstention_rate": 0.5,
            "unsupported_claim_rate": 0.5,
            "retry_rate": 1.0,
            "route_switch_rate": 0.5,
        }
    ]


def test_observability_separates_retrieval_retry_and_verifier_recovery():
    recovery = {
        "stage": "reverify",
        "verifier_recovery_attempt": 1,
        "failure_type": "required_boolean_authority_missing",
        "retry_reason": "required_boolean_authority_missing",
    }
    prediction = {
        "controller_trace": [
            {"stage": "retrieval", "action": "retrieval_retry", "retry": True},
            dict(recovery, stage="critic"),
            dict(recovery, stage="focused_retrieval"),
            dict(recovery, stage="evidence_rebind"),
            recovery,
        ],
        "agent_trace": [dict(recovery, stage="agent_reverify")],
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["retrieval_retry_count"] == 1
    assert observability["verifier_recovery_count"] == 1
    assert observability["route_switch_count"] == 0


def test_observability_counts_implicit_second_retrieval_round_only_once():
    prediction = {
        "evidence_metadata": {"retrieval_rounds": 2},
        "controller_trace": [
            {
                "stage": "retrieval_evaluator",
                "status": "good",
                "retry": False,
            }
        ],
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["retrieval_retry_count"] == 1
    assert observability["verifier_recovery_count"] == 0


def test_observability_keeps_route_switch_separate_from_recovery_transition():
    transition = {
        "stage": "route_switch",
        "transition_id": "verifier-recovery:1:doc_text->hybrid",
        "from_route": "doc_text",
        "to_route": "hybrid",
        "verifier_recovery_attempt": 1,
        "failure_type": "required_boolean_authority_missing",
    }
    prediction = {
        "controller_trace": [transition, dict(transition, stage="agent")],
        "workflow_plan": {"events": [dict(transition, stage="planner")]},
    }

    observability = prediction_verifier_observability(prediction)

    assert observability["route_switch_count"] == 1
    assert observability["verifier_recovery_count"] == 1
