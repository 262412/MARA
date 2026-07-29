from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa.query_planning import build_query_plan, score_evidence_for_slot

from benchmark.answer_finalizer import attach_structured_citations_from_evidence
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_candidate_state import select_answerability_candidate
from benchmark.qasper_prompt_budget import fit_qasper_verifier_items
from benchmark.task_answer_contracts import apply_task_answer_contract
from scripts.slurm.validate_contract_smoke import QASPER_HARD_GATES


class _VerifierLLM:
    def __init__(self, payload: dict[str, str]):
        self.payload = payload
        self.prompts: list[str] = []

    def __call__(self, prompt: str, **_kwargs: Any) -> SimpleNamespace:
        self.prompts.append(prompt)
        return SimpleNamespace(text=json.dumps(self.payload))


def _item(local_id: str, text: str, **metadata: Any) -> dict[str, Any]:
    return {
        "source_id": "paper",
        "evidence_id": local_id,
        "text": text,
        **metadata,
    }


def test_product_abstention_uses_pre_guardrail_candidate_for_answerability():
    refusal = "MARA could not retrieve enough evidence to answer this question."
    support = _item(
        "support",
        "The classification model uses manually provided labeled features.",
    )
    prediction: dict[str, Any] = {
        "question": "What background knowledge does the classification model use?",
        "predicted_answer": refusal,
        "answer_for_scoring": refusal,
        "answer_type": "free_text",
        "guardrail_decision": {"action": "abstain"},
        "evidence_bundle": {"items": [support], "metadata": {}},
        "evidence_metadata": {
            "pre_guardrail_answer": "manually provided labeled features",
            "generation_context_evidence": [support],
        },
    }
    llm = _VerifierLLM(
        {
            "verdict": "supported",
            "evidence_quote": support["text"],
            "revised_answer": "",
        }
    )

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: llm,
    )

    trace = prediction["evidence_metadata"]["answerability_contract_trace"]
    assert prediction["predicted_answer"] == "manually provided labeled features"
    assert trace["input_candidate_kind"] == "pre_guardrail_answer"
    assert trace["product_answer"] == refusal
    assert trace["candidate_for_answerability"] == (
        "manually provided labeled features"
    )
    assert trace["recovery_attempted"] is True
    assert trace["recovery_result"] == "recovered"
    assert trace["final_post_contract_answer"] == prediction["predicted_answer"]
    assert all(refusal not in prompt for prompt in llm.prompts)


def test_product_abstention_without_original_candidate_is_preserved():
    refusal = "MARA could not retrieve enough evidence to answer this question."
    prediction: dict[str, Any] = {
        "question": "What background knowledge do they use?",
        "predicted_answer": refusal,
        "answer_for_scoring": refusal,
        "guardrail_decision": {"action": "abstain"},
        "evidence_metadata": {},
    }
    candidate = select_answerability_candidate(prediction)

    assert candidate.candidate_for_answerability == ""
    assert candidate.input_candidate_kind == "missing_original_candidate"
    assert candidate.recovery_attempted is False
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("verifier must not generate a missing candidate")
        ),
    )
    assert prediction["predicted_answer"] == refusal


def test_multiline_unanswerable_explanation_is_not_a_recovery_candidate():
    refusal = "MARA could not retrieve enough evidence to answer this question."
    generated_abstention = (
        "unanswerable\n"
        "The provided context does not mention experiments conducted by the authors."
    )
    prediction: dict[str, Any] = {
        "question": "Do the authors conduct experiments on the tasks mentioned?",
        "predicted_answer": refusal,
        "answer_for_scoring": refusal,
        "guardrail_decision": {"action": "abstain"},
        "evidence_metadata": {
            "pre_guardrail_answer": generated_abstention,
            "pre_verification_answer": generated_abstention,
        },
    }

    candidate = select_answerability_candidate(prediction)

    assert candidate.input_candidate_kind == "missing_original_candidate"
    assert candidate.candidate_for_answerability == ""
    assert candidate.recovery_attempted is False


def test_required_verifier_evidence_is_not_dropped_by_budget_packing():
    support = _item(
        "late-support",
        "The classification model uses manually provided labeled features.",
    )
    noise = [
        _item(f"noise-{index}", f"Unrelated discussion {index}. " + ("x " * 900))
        for index in range(5)
    ]

    _prompt, bounded, trace = fit_qasper_verifier_items(
        [*noise, support],
        lambda evidence: f"QUESTION\n{evidence}",
        question="What background knowledge does the model use?",
        candidate_answer="manually provided labeled features",
        required_evidence_ids=["evidence:paper:late-support"],
    )

    assert support["text"] in bounded
    assert trace["verifier_required_evidence_ids"] == "evidence:paper:late-support"
    assert trace["verifier_required_evidence_coverage"] == "1.000000"


def test_supported_core_is_pruned_when_extension_breaks_whole_answer_relation():
    evidence = "The classification model uses manually provided labeled features."
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "supported",
                "evidence_quote": evidence,
                "revised_answer": "",
            }
        ),
        question="What background knowledge does the classification model use?",
        evidence=evidence,
        candidate_answer=(
            "manually provided labeled features and an undocumented graph module"
        ),
    )

    assert result.answer == "manually provided labeled features"
    assert result.trace["verdict"] == "supported_with_pruning"
    assert result.trace["action"] == "pruned_unsupported_extension"


def test_grounded_core_is_pruned_even_when_whole_answer_verdict_is_unsupported():
    quote = (
        "A labeled feature is a strong indicator of a specific class and is "
        "manually provided to the classifier."
    )
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "unsupported",
                "evidence_quote": quote,
                "revised_answer": "",
            }
        ),
        question="What background knowledge do they leverage?",
        evidence=quote,
        candidate_answer=(
            "Labeled features are manually provided indicators of specific classes. "
            "Class distribution is also used to guide predictions."
        ),
    )

    assert result.answer == (
        "Labeled features are manually provided indicators of specific classes"
    )
    assert result.trace["verdict"] == "supported_with_pruning"
    assert result.trace["action"] == "pruned_unsupported_extension"


def test_qasper_boolean_slot_rejects_cited_work_and_selects_current_scope():
    plan = build_query_plan(
        "Do they report results only on English data?",
        answer_type="boolean",
        verification_domain="qasper",
    )
    slot = plan.evidence_slots[0]
    cited_work = _item(
        "related",
        (
            "Goudas et al. 2014 evaluated user-generated Greek texts in "
            "previous work."
        ),
        section_id="related_work",
    )
    current_scope = _item(
        "current",
        (
            "As a main field of interest in the current study, we identified "
            "controversial topics in education in English-speaking countries."
        ),
    )

    assert slot.statement_kind == "boolean_proposition"
    assert "current study" in slot.query.lower()
    assert score_evidence_for_slot(slot, cited_work) == 0.0
    assert score_evidence_for_slot(slot, current_scope) > 0.0


def test_related_work_non_english_evidence_cannot_support_current_paper_no():
    quote = (
        "Previous work by Goudas et al. evaluated user-generated Greek texts "
        "and reported multilingual results."
    )
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "no_complete",
                "evidence_quote": quote,
            }
        ),
        question="Do they report results only on English data?",
        evidence=quote,
        evidence_items=[
            _item("related", quote, section_id="related_work"),
        ],
        candidate_answer="no",
    )

    assert result.answer == "unanswerable"
    assert result.trace["boolean_actor"] == "cited_work"
    assert result.trace["boolean_section_role"] == "related_work"
    assert result.trace["boolean_scope_valid"] == "false"


def test_current_paper_closed_english_experiment_supports_yes():
    quote = "We report experiments on English datasets X and Y only."
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "yes_complete",
                "evidence_quote": quote,
            }
        ),
        question="Do they report results only on English data?",
        evidence=quote,
        evidence_items=[
            _item("experiments", quote, section_id="experiments"),
        ],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["boolean_scope_valid"] == "true"


def test_current_paper_non_english_counterexample_supports_no():
    quote = "We additionally evaluate the model on a Greek dataset in our experiments."
    result = verify_qasper_answerability(
        _VerifierLLM(
            {
                "verdict": "no_complete",
                "evidence_quote": quote,
            }
        ),
        question="Do they report results only on English data?",
        evidence=quote,
        evidence_items=[
            _item("experiments", quote, section_id="experiments"),
        ],
        candidate_answer="unanswerable",
    )

    assert result.answer == "no"
    assert result.trace["boolean_scope_valid"] == "true"


def test_simple_boolean_citation_uses_minimum_scope_valid_support_set():
    related = _item(
        "related",
        "Previous work evaluated Greek data.",
        section_id="related_work",
    )
    current = _item(
        "current",
        "We report experiments on English datasets X and Y only.",
        section_id="experiments",
    )
    prediction: dict[str, Any] = {
        "question": "Do they report results only on English data?",
        "predicted_answer": "yes",
        "answer_type": "boolean",
        "evidence_bundle": {
            "items": [related, current],
            "metadata": {
                "verified_claim_support_by_claim": {
                    "claim:1": [
                        "evidence:paper:related",
                        "evidence:paper:current",
                    ]
                }
            },
        },
        "evidence_metadata": {},
    }

    citations = attach_structured_citations_from_evidence(prediction, span="yes")

    assert len(citations) == 1
    assert citations[0]["evidence_id"] == "evidence:paper:current"


def test_qasper_smoke_metrics_expose_new_hard_gate_invariants():
    refusal = "MARA could not retrieve enough evidence to answer this question."
    prediction = {
        "question": "Do they report results only on English data?",
        "gold_answers": ["yes"],
        "predicted_answer": refusal,
        "answer_for_scoring": refusal,
        "answer_type": "boolean",
        "evidence_metadata": {
            "qasper_answerability": {
                "input_candidate_kind": "product_answer",
                "candidate_for_answerability": refusal,
                "verifier_required_evidence_coverage": "0.500000",
            }
        },
    }
    scope_violation = {
        "question": "Do they report results only on English data?",
        "gold_answers": ["yes"],
        "predicted_answer": "no",
        "answer_for_scoring": "no",
        "answer_type": "boolean",
        "evidence_metadata": {
            "qasper_answerability": {
                "candidate_for_answerability": "no",
                "boolean_scope_valid": "false",
            }
        },
    }

    summary = contract_invariant_summary([prediction, scope_violation])

    assert summary["abstention_candidate_sent_as_semantic_answer_count"] == 1.0
    assert summary["verifier_required_evidence_coverage"] == 0.5
    assert summary["answerable_false_abstention_count"] == 1.0
    assert summary["boolean_scope_violation_count"] == 1.0


def test_citation_metrics_separate_support_scope_and_minimality():
    current = _item(
        "current",
        "We report experiments on English datasets X and Y only.",
        section_id="experiments",
    )
    related = _item(
        "related",
        "Previous work evaluated Greek data.",
        section_id="related_work",
    )
    prediction = {
        "question": "Do they report results only on English data?",
        "gold_answers": ["yes"],
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_type": "boolean",
        "evidence_metadata": {
            "canonical_candidate_evidence": [current, related],
            "verified_claim_support_evidence": [current],
            "emitted_citation_evidence": [current, related],
            "qasper_answerability": {
                "candidate_for_answerability": "yes",
                "boolean_scope_valid": "true",
            },
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["citation_claim_support_violation_count"] == 1.0
    assert summary["citation_scope_violation_count"] == 1.0
    assert summary["citation_nonminimal_count"] == 1.0
    assert summary["wrong_polarity_count"] == 0.0


def test_qasper_contract_smoke_declares_all_new_hard_gates():
    assert {
        "abstention_candidate_sent_as_semantic_answer_count",
        "verifier_required_evidence_coverage",
        "answerable_false_abstention_count",
        "boolean_scope_violation_count",
        "wrong_polarity_count",
        "citation_claim_support_violation_count",
        "citation_scope_violation_count",
    } <= set(QASPER_HARD_GATES)
