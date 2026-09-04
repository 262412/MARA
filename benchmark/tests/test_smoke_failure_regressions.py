from __future__ import annotations

from benchmark.answerability_trace import normalized_answerability_trace
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.metrics import (
    is_abstention_answer,
    legacy_token_f1_score,
    token_f1_score,
)
from benchmark.scoring import score_prediction


def test_token_f1_v2_does_not_share_characters_between_latin_words():
    assert token_f1_score("unanswerable", ["true"]) == 0.0
    assert token_f1_score("unanswerable", ["false"]) == 0.0
    assert token_f1_score("unanswerable", ["true", "false"]) == 0.0
    assert token_f1_score("unanswerable", ["unanswerable"]) == 1.0
    assert legacy_token_f1_score("unanswerable", ["true"]) > 0.0


def test_abstention_fallback_is_precise_and_covers_runtime_refusals():
    assert is_abstention_answer("unanswerable") is True
    assert (
        is_abstention_answer(
            "MARA could not retrieve enough evidence to answer this question."
        )
        is True
    )
    assert is_abstention_answer("当前文档没有足够证据回答该问题。") is True
    assert (
        is_abstention_answer(
            "The paper studies how annotators classify unanswerable questions."
        )
        is False
    )


def test_citation_headline_does_not_fall_back_to_retrieved_sources():
    metrics = score_prediction(
        {
            "gold_answers": ["42"],
            "predicted_answer": "42",
            "predicted_pages": [5],
            "gold_pages": [5],
            "predicted_sources": ["doc#page:5"],
            "predicted_citations": [],
            "structured_citations": [],
            "gold_sources": ["doc#page:5"],
            "gold_evidence": [
                {"document_id": "doc", "citation": "doc#page:5", "page": 5}
            ],
            "expected_formats": [],
            "expected_guardrails": {},
            "claim_verification": {},
            "verify_decision": {"status": "supported"},
            "guardrail_decision": {"status": "supported", "action": "return"},
            "evidence_metadata": {"emitted_citation_evidence": []},
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

    assert metrics["citation_recall"] == 0.0
    assert metrics["citation_precision"] is None
    assert metrics["citation_recall_page"] == 0.0
    assert metrics["citation_precision_page"] is None


def test_contract_summary_reports_non_vacuous_stage_and_citation_coverage():
    prediction = {
        "question": "What result is reported?",
        "answer_type": "free_text",
        "predicted_answer": "The result was positive.",
        "gold_answers": ["The result was positive."],
        "gold_evidence": [{"document_id": "paper", "page": 1}],
        "evidence_metadata": {
            "canonical_candidate_evidence": [],
            "selected_evidence": [],
            "generation_context_evidence": [],
            "emitted_citation_evidence": [],
            "ranking_trace": {"backend_execution": False},
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["required_candidate_nonempty_rate"] == 0.0
    assert summary["required_selected_nonempty_rate"] == 0.0
    assert summary["required_generation_context_nonempty_rate"] == 0.0
    assert summary["citation_required_example_count"] == 1.0
    assert summary["citation_emitted_example_count"] == 0.0
    assert summary["required_citation_missing_count"] == 1.0
    assert summary["citation_emission_coverage"] == 0.0
    assert summary["reranker_execution_coverage"] is None
    assert summary["contract_gates"]["reranker_lineage"]["status"] == ("not_applicable")
    assert summary["contract_gates"]["citation_emission"]["status"] == "failed"
    assert summary["contract_gates"]["evidence_stage_nonempty"]["status"] == "failed"


def test_legacy_answerability_trace_uses_pre_verification_claims_not_primary_answer():
    prediction = {
        "predicted_answer": "unanswerable",
        "pre_contract_verification": {
            "verify_decision": {"claims": ["Answer: No."]},
        },
        "post_contract_verification": {"answer": "unanswerable"},
        "evidence_metadata": {
            "qasper_answerability": {
                "action": "abstained_unsupported_candidate",
            }
        },
    }

    trace = normalized_answerability_trace(prediction)

    assert trace["pre_contract_answer"] == "Answer: No."
    assert trace["post_contract_answer"] == "unanswerable"
    assert trace["rewrite_applied"] is True
    assert trace["trace_source"] == "legacy_pre_post_verification"
