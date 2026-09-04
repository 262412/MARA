from benchmark.scoring import score_prediction


def test_score_prediction_uses_scored_metadata_citations_when_available():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42",
            "predicted_pages": [5, 99, 100],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5", "doc#page:99", "doc#page:100"],
            "scored_predicted_sources": ["doc#page:5"],
            "predicted_citations": [],
            "gold_sources": ["doc#page:5"],
            "gold_evidence": [
                {"document_id": "doc", "citation": "doc#page:5", "page": 5}
            ],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {"status": "supported"},
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "5",
                    "source_backrefs": ["doc#page:5"],
                },
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "99",
                    "source_backrefs": ["doc#page:99"],
                },
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "100",
                    "source_backrefs": ["doc#page:100"],
                },
            ],
        }
    )

    assert metrics["citation_metadata_recall"] == 1.0
    assert metrics["citation_metadata_precision"] == 1.0
    assert metrics["citation_recall"] == 0.0
    assert metrics["citation_precision"] is None


def test_score_prediction_uses_structured_citations_as_inline_citations():
    metrics = score_prediction(
        {
            "gold_answers": ["Market size"],
            "predicted_answer": "Market size",
            "predicted_pages": [3],
            "gold_pages": [3],
            "predicted_sources": ["deck#page:3"],
            "predicted_citations": [],
            "structured_citations": [
                {"source_id": "deck", "page_label": "3", "span": "Market size"}
            ],
            "gold_sources": ["deck#page:3"],
            "gold_evidence": [
                {
                    "document_id": "deck",
                    "source_id": "deck",
                    "page_label": "3",
                    "span": "Market size",
                }
            ],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {"status": "supported"},
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {},
            "evidence_bundle": {},
            "retrieved_hits": [
                {
                    "document_id": "deck",
                    "source_id": "deck",
                    "page_label": "3",
                    "text": "Market size",
                    "source_backrefs": ["deck#page:3"],
                }
            ],
        }
    )

    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_inline_recall"] == 0.0
    assert metrics["citation_inline_precision"] is None
