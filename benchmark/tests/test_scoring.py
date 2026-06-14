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


def test_score_prediction_scores_final_answer_without_rendered_thought_details():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": (
                "<details><summary><span style='color:grey'>Thought</span>"
                "</summary><blockquote>The unsupported scratch value is 12."
                "</blockquote></details>\n\n42"
            ),
            "predicted_pages": [5],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5"],
            "gold_sources": ["doc#page:5"],
            "gold_evidence": [{"citation": "doc#page:5", "page": 5, "span": "42"}],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {
                "status": "supported",
                "verified_citations": ["doc#page:5"],
            },
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [],
        }
    )

    assert metrics["em"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["numeric_match"] == 1.0


def test_score_prediction_scores_markdown_final_answer_without_untagged_thought():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": (
                "Thought The scratch value is 12.\n\n" "**Final Answer**: 42"
            ),
            "predicted_pages": [5],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5"],
            "gold_sources": ["doc#page:5"],
            "gold_evidence": [{"citation": "doc#page:5", "page": 5, "span": "42"}],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {
                "status": "supported",
                "verified_citations": ["doc#page:5"],
            },
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [],
        }
    )

    assert metrics["em"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["numeric_match"] == 1.0


def test_score_prediction_ignores_markdown_table_when_table_format_not_expected():
    metrics = score_prediction(
        {
            "gold_answers": [
                "Richard A. Johnson received the highest number of votes against."
            ],
            "predicted_answer": (
                "| Nominee | Votes Against |\n"
                "| --- | ---: |\n"
                "| Richard A. Johnson | 16,105,005 |\n"
                "| Dona D. Young | 6,074,467 |\n\n"
                "Richard A. Johnson received the highest number of votes against."
            ),
            "predicted_pages": [2],
            "gold_pages": [2],
            "predicted_sources": ["doc#page:2"],
            "gold_sources": ["doc#page:2"],
            "gold_evidence": [
                {
                    "citation": "doc#page:2",
                    "page": 2,
                    "span": "Richard A. Johnson received the highest number.",
                }
            ],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {
                "status": "supported",
                "verified_citations": ["doc#page:2"],
            },
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [],
        }
    )

    assert metrics["f1"] == 1.0
