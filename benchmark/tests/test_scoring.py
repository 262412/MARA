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


def test_score_prediction_uses_clean_final_answer_for_abstention_correctness():
    metrics = score_prediction(
        {
            "gold_answers": ["Revenue increased in 2026."],
            "predicted_answer": (
                "<think>MARA could not retrieve enough evidence to answer "
                "reliably.</think>\n\n"
                "Final answer: Revenue increased in 2026."
            ),
            "predicted_pages": [2],
            "gold_pages": [2],
            "predicted_sources": ["doc#page:2"],
            "gold_sources": ["doc#page:2"],
            "gold_evidence": [
                {
                    "citation": "doc#page:2",
                    "page": 2,
                    "span": "Revenue increased in 2026.",
                }
            ],
            "expected_formats": [],
            "expected_guardrails": {"allow_abstention": False},
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

    assert metrics["em"] == 1.0
    assert metrics["abstained"] == 0.0
    assert metrics["abstention_correctness"] == 1.0


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


def test_score_prediction_counts_source_level_citation_when_gold_span_is_retrieved():
    metrics = score_prediction(
        {
            "gold_answers": ["The proposed method improves recall."],
            "predicted_answer": "The proposed method improves recall.",
            "predicted_pages": [],
            "gold_pages": [],
            "predicted_sources": ["paper-1#source"],
            "gold_sources": [],
            "gold_evidence": [
                {
                    "document_id": "paper-1",
                    "citation": "paper-1#evidence:1",
                    "span": "The proposed method improves recall.",
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
                    "document_id": "paper-1",
                    "source_id": "paper-1",
                    "text": "The proposed method improves recall.",
                    "source_backrefs": ["paper-1#source"],
                }
            ],
        }
    )

    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_recall_source"] == 1.0
    assert metrics["citation_precision_source"] == 1.0
    assert metrics["citation_recall_span"] == 1.0
    assert metrics["citation_precision_span"] == 1.0


def test_score_prediction_reports_page_level_citation_submetrics():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42",
            "predicted_pages": [5],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5"],
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
                }
            ],
        }
    )

    assert metrics["citation_recall_page"] == 1.0
    assert metrics["citation_precision_page"] == 1.0


def test_score_prediction_uses_emitted_citations_not_retrieved_source_coverage():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42 [doc#page:5]",
            "predicted_pages": [5, 99, 100],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5", "doc#page:99", "doc#page:100"],
            "predicted_citations": ["doc#page:5"],
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

    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_recall_page"] == 1.0
    assert metrics["citation_precision_page"] == 1.0


def test_score_prediction_reports_inline_and_metadata_citation_metrics_separately():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42 [doc#page:5]",
            "predicted_pages": [5, 99],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5", "doc#page:99"],
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
            ],
        }
    )

    assert metrics["citation_inline_recall"] == 1.0
    assert metrics["citation_inline_precision"] == 1.0
    assert metrics["citation_metadata_recall"] == 1.0
    assert metrics["citation_metadata_precision"] == 0.5
    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0


def test_score_prediction_falls_back_to_sources_when_emitted_citations_are_empty():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42",
            "predicted_pages": [5],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5"],
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
                }
            ],
        }
    )

    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_recall_page"] == 1.0
    assert metrics["citation_precision_page"] == 1.0


def test_score_prediction_aligns_parser_page_when_visual_quote_is_retrieved():
    metrics = score_prediction(
        {
            "gold_answers": ["Zone AMS sales were CHF 34.0 billion."],
            "predicted_answer": "Zone AMS sales were CHF 34.0 billion.",
            "predicted_pages": ["59"],
            "gold_pages": [58],
            "predicted_sources": ["doc#page:59"],
            "gold_sources": ["doc#page:58"],
            "gold_evidence": [
                {
                    "document_id": "doc",
                    "citation": "doc#page:58",
                    "page": 58,
                    "element_type": "table",
                    "image_quote": (
                        "The Zone AMS table reports sales of CHF 34.0 billion, "
                        "organic growth of 4.8%, real internal growth of 4.1%, "
                        "and sales for United States and Canada and Latin "
                        "America and Caribbean."
                    ),
                }
            ],
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "59",
                    "source_backrefs": ["doc#page:59"],
                    "text": (
                        "Zone Americas (AMS). Zone AMS in millions of CHF. "
                        "Sales 2020 34.0 billion. Organic growth 4.8%, real "
                        "internal growth 4.1%. United States and Canada, "
                        "Latin America and Caribbean."
                    ),
                }
            ],
            "evidence_bundle": {"items": []},
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
        }
    )

    assert metrics["page_hit"] == 1.0
    assert metrics["citation_recall"] == 1.0
    assert metrics["citation_precision"] == 1.0
    assert metrics["citation_recall_page"] == 1.0
    assert metrics["citation_precision_page"] == 1.0


def test_score_prediction_keeps_wrong_parser_page_without_gold_quote_support():
    metrics = score_prediction(
        {
            "gold_answers": ["Zone AMS sales were CHF 34.0 billion."],
            "predicted_answer": "Zone AMS sales were CHF 34.0 billion.",
            "predicted_pages": ["59"],
            "gold_pages": [58],
            "predicted_sources": ["doc#page:59"],
            "gold_sources": ["doc#page:58"],
            "gold_evidence": [
                {
                    "document_id": "doc",
                    "citation": "doc#page:58",
                    "page": 58,
                    "element_type": "table",
                    "image_quote": (
                        "The Zone AMS table reports sales of CHF 34.0 billion, "
                        "organic growth of 4.8%, and real internal growth of 4.1%."
                    ),
                }
            ],
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "59",
                    "source_backrefs": ["doc#page:59"],
                    "text": "A different page about corporate governance and board members.",
                }
            ],
            "evidence_bundle": {"items": []},
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
        }
    )

    assert metrics["page_hit"] == 0.0
    assert metrics["citation_recall"] == 0.0
    assert metrics["citation_precision"] == 0.0


def test_score_prediction_requires_nearby_page_for_quote_based_alignment():
    metrics = score_prediction(
        {
            "gold_answers": ["Zone AMS sales were CHF 34.0 billion."],
            "predicted_answer": "Zone AMS sales were CHF 34.0 billion.",
            "predicted_pages": ["2"],
            "gold_pages": [58],
            "predicted_sources": ["doc#page:2"],
            "gold_sources": ["doc#page:58"],
            "gold_evidence": [
                {
                    "document_id": "doc",
                    "citation": "doc#page:58",
                    "page": 58,
                    "element_type": "table",
                    "image_quote": (
                        "The table presents financial metrics including sales, "
                        "organic growth, real internal growth, underlying "
                        "trading operating profit margin, and trading operating "
                        "profit margin."
                    ),
                }
            ],
            "retrieved_hits": [
                {
                    "document_id": "doc",
                    "source_id": "doc",
                    "page_label": "2",
                    "source_backrefs": ["doc#page:2"],
                    "text": (
                        "The shareholder letter summarizes financial metrics, "
                        "organic growth, real internal growth, sales, "
                        "underlying trading operating profit margin, and "
                        "trading operating profit margin."
                    ),
                }
            ],
            "evidence_bundle": {"items": []},
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
        }
    )

    assert metrics["page_hit"] == 0.0
    assert metrics["citation_recall"] == 0.0
    assert metrics["citation_precision"] == 0.0


def test_score_prediction_rejects_source_level_citation_without_retrieved_gold_span():
    metrics = score_prediction(
        {
            "gold_answers": ["The proposed method improves recall."],
            "predicted_answer": "The proposed method improves recall.",
            "predicted_pages": [],
            "gold_pages": [],
            "predicted_sources": ["paper-1#source"],
            "gold_sources": [],
            "gold_evidence": [
                {
                    "document_id": "paper-1",
                    "citation": "paper-1#evidence:1",
                    "span": "The proposed method improves recall.",
                }
            ],
            "retrieved_hits": [
                {
                    "document_id": "paper-1",
                    "source_id": "paper-1",
                    "text": "Same source but unrelated paragraph.",
                }
            ],
            "evidence_bundle": {"items": []},
            "claim_verification": {},
            "expected_guardrails": {},
            "expected_formats": [],
        }
    )

    assert metrics["citation_recall"] == 0.0
    assert metrics["citation_precision"] == 0.0
