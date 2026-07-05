from benchmark.scoring import score_prediction


def test_score_prediction_does_not_count_revise_as_abstention():
    metrics = score_prediction(
        {
            "gold_answers": ["No"],
            "predicted_answer": "No, the company is not a high growth company.",
            "predicted_pages": [7],
            "gold_pages": [7],
            "predicted_sources": ["JNJ_2022_10K#page:7"],
            "gold_sources": ["JNJ_2022_10K#page:7"],
            "gold_evidence": [
                {
                    "citation": "JNJ_2022_10K#page:7",
                    "page": 7,
                    "span": "Sales grew by 1.3% in FY2022.",
                }
            ],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {
                "status": "unsupported",
                "unsupported_claims": [
                    "The company is not a high growth company."
                ],
            },
            "guardrail_decision": {
                "status": "unsupported",
                "action": "revise",
            },
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [],
        }
    )

    assert metrics["abstained"] == 0.0
    assert metrics["false_abstention"] == 0.0
    assert metrics["unsupported_claim_rate"] == 1.0
