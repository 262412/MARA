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
