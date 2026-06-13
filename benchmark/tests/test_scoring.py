from benchmark.scoring import score_prediction


def test_score_prediction_counts_guardrail_abstain_as_abstention():
    metrics = score_prediction(
        {
            "gold_answers": ["$1,577.00"],
            "predicted_answer": (
                "MARA could not retrieve enough evidence to answer reliably."
            ),
            "predicted_pages": [],
            "gold_pages": [59],
            "predicted_sources": [],
            "gold_sources": ["3M_2018_10K#page:59"],
            "gold_evidence": [{"citation": "3M_2018_10K#page:59", "page": 59}],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {
                "status": "not_enough_evidence",
                "verified_citations": [],
            },
            "guardrail_decision": {
                "status": "not_enough_evidence",
                "action": "abstain",
            },
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [],
        }
    )

    assert metrics["abstained"] == 1.0
    assert metrics["false_abstention"] == 1.0
    assert metrics["not_enough_evidence_rate"] == 1.0
