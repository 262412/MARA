from types import SimpleNamespace
from typing import Any

from benchmark.qasper_answerability import verify_qasper_answerability


class _VerifierLLM:
    def __init__(self, response: str | list[str]):
        self.responses = [response] if isinstance(response, str) else list(response)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        return SimpleNamespace(text=self.responses.pop(0))


class _ContextLimitedVerifierLLM(_VerifierLLM):
    def __call__(self, prompt: str, **kwargs):
        if len(prompt) > 7000:
            raise RuntimeError("verifier prompt exceeds the local model budget")
        return super().__call__(prompt, **kwargs)


def test_qasper_answerability_bounds_long_retrieved_evidence_before_llm_call():
    quote = "The authors released their source code with the paper."
    llm = _ContextLimitedVerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":' f'"{quote}"}}'
    )
    evidence = "\n\n".join([quote, *(["unrelated evidence " * 120] * 80)])

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence=evidence,
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert len(llm.calls) == 1
    assert len(llm.calls[0][0]) <= 7000
    assert result.trace["evidence_budget_status"] == "item_packed"
    assert int(result.trace["evidence_chars_used"]) < int(
        result.trace["evidence_chars_original"]
    )


def test_qasper_verifier_packs_late_relevant_item_without_partial_items():
    quote = "The classification model uses labeled features."
    llm = _ContextLimitedVerifierLLM(
        '{"verdict":"supported","evidence_quote":' f'"{quote}",' '"revised_answer":""}'
    )
    evidence_items = [
        {
            "source_id": "paper",
            "span_id": f"noise-{index}",
            "text": f"Unrelated appendix material {index}. " * 80,
        }
        for index in range(20)
    ]
    evidence_items.append(
        {
            "source_id": "paper",
            "span_id": "answer",
            "text": quote,
        }
    )

    result = verify_qasper_answerability(
        llm,
        question="What features does the classification model use?",
        evidence="",
        evidence_items=evidence_items,
        required_evidence_ids=["span:paper:answer"],
        candidate_answer="labeled features",
    )

    prompt = llm.calls[0][0]
    assert result.answer == "labeled features"
    assert quote in prompt
    assert result.trace["verifier_input_evidence_ids"].split(",")[0] == (
        "span:paper:answer"
    )
    assert "span:paper:noise-19" in result.trace["verifier_dropped_evidence_ids"]
    assert result.trace["verifier_budget_exhausted"] == "true"
    assert not prompt.rstrip().endswith("Unrelated appendix")


def test_qasper_answerability_rejects_related_but_unsupported_candidate():
    llm = _VerifierLLM(
        '{"verdict":"unsupported","evidence_quote":"The paper reports NDCG 55.46."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="What was the baseline?",
        evidence=(
            "The paper reports NDCG 55.46 for the proposed system, but does "
            "not identify a baseline."
        ),
        candidate_answer="The baseline was NDCG 55.46.",
    )

    assert result.answer == "unanswerable"
    assert result.trace["status"] == "ok"
    assert result.trace["verdict"] == "unsupported"
    assert "Topic overlap or a plausible answer is not sufficient" in llm.calls[0][0]
    assert llm.calls[0][1]["temperature"] == 0
    assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True


def test_qasper_answerability_preserves_supported_candidate():
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":'
        '"The system is evaluated using cosine similarity."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Which metric evaluates the system?",
        evidence="The system is evaluated using cosine similarity.",
        candidate_answer="cosine similarity",
    )

    assert result.answer == "cosine similarity"
    assert result.trace["verdict"] == "supported"


def test_qasper_answerability_prunes_latex_extension_to_grounded_phrase():
    quote = (
        "We address the robustness problem using a method which leverages "
        "labeled features as prior knowledge."
    )
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":' f'"{quote}","revised_answer":""}}'
    )

    result = verify_qasper_answerability(
        llm,
        question="What background knowledge do they leverage?",
        evidence=quote,
        candidate_answer=(
            "$$ \\text{Background knowledge} = \\text{labeled features} + "
            "\\text{class distribution} + \\text{neutral features} $$"
        ),
    )

    assert result.answer == "labeled features"
    assert result.trace["verdict"] == "supported_with_pruning"
    assert result.trace["action"] == "pruned_unsupported_extension"


def test_qasper_answerability_rejects_supported_verdict_without_grounded_quote():
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":'
        '"The system is evaluated using BLEU."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Which metric evaluates the system?",
        evidence="The system is evaluated using cosine similarity.",
        candidate_answer="BLEU",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "unsupported"
    assert result.trace["action"] == "abstained_ungrounded_quote"


def test_qasper_answerability_rejects_grounded_quote_without_question_relation():
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":'
        '"Cosine similarity compares unrelated embedding vectors."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Which metric evaluates the PolyResponse system?",
        evidence=(
            "Cosine similarity compares unrelated embedding vectors. "
            "PolyResponse is discussed in a separate experiment."
        ),
        candidate_answer="cosine similarity",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "unsupported"
    assert result.trace["action"] == "abstained_ungrounded_quote"


def test_qasper_answerability_does_not_rejudge_explicit_unanswerable():
    llm = _VerifierLLM(
        '{"verdict":"supported","evidence_quote":"No baseline is described."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="What was the baseline?",
        evidence="No baseline is described.",
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["status"] == "not_required"
    assert llm.calls == []


def test_qasper_answerability_checks_boolean_question_sufficiency_not_token_support():
    llm = _VerifierLLM(
        '{"verdict":"no","evidence_quote":'
        '"The embeddings can be used as a drop-in replacement in existing models."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Is fine-tuning required?",
        evidence=(
            "The embeddings can be used as a drop-in replacement in existing models."
        ),
        candidate_answer="no",
    )

    assert result.answer == "no"
    assert result.trace["status"] == "ok"
    assert result.trace["verdict"] == "no"
    assert "Compare the complete yes/no question proposition" in llm.calls[0][0]
    assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True


def test_qasper_answerability_corrects_yes_candidate_on_grounded_no_verdict():
    llm = _VerifierLLM(
        '{"verdict":"no","evidence_quote":'
        '"The method is used as a drop-in replacement and requires no fine-tuning."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the method require fine-tuning?",
        evidence=(
            "The method is used as a drop-in replacement and requires no "
            "fine-tuning."
        ),
        candidate_answer="yes",
    )

    assert result.answer == "no"
    assert result.trace["verdict"] == "no"
    assert result.trace["action"] == "corrected_polarity"
    assert "CANDIDATE ANSWER" not in llm.calls[0][0]


def test_qasper_answerability_corrects_no_candidate_on_grounded_yes_verdict():
    llm = _VerifierLLM(
        '{"verdict":"yes","evidence_quote":'
        '"The authors released their source code with the paper."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence="The authors released their source code with the paper.",
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["verdict"] == "yes"
    assert result.trace["action"] == "corrected_polarity"


def test_qasper_answerability_abstains_on_incomplete_conflicting_verdict():
    llm = _VerifierLLM(
        '{"verdict":"no_complete","evidence_quote":'
        '"The model uses attention over the encoded input sequence."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Do they use attention?",
        evidence="The model uses attention over the encoded input sequence.",
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "abstained_insufficient_evidence"
    assert result.trace["primary_answer"] == "yes"
    assert result.trace["adjudicated_polarity"] == "insufficient_evidence"
    assert result.trace["reason"] == "current_paper_scope_not_established"


def test_qasper_boolean_abstains_when_verifier_cannot_bind_a_complete_quote():
    llm = _VerifierLLM('{"verdict":"insufficient_evidence","evidence_quote":""}')

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence=(
            "The authors released their source code with the paper. "
            "The appendix discusses unrelated licensing concerns."
        ),
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["action"] == "abstained_insufficient_evidence"
    assert result.trace["conflict_status"] == "insufficient_evidence"
    assert float(result.trace["candidate_support_score"]) > 0
    assert float(result.trace["contradiction_score"]) == 0


def test_qasper_boolean_abstains_when_direct_polarities_are_balanced():
    llm = _VerifierLLM(
        '{"verdict":"no_complete","evidence_quote":'
        '"The authors did not release the code with the paper."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence=(
            "The authors released the code with the paper. "
            "The authors did not release the code with the paper."
        ),
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["action"] == "abstained_polarity_conflict"
    assert result.trace["conflict_status"] == "balanced_conflict"


def test_qasper_boolean_question_reconsiders_primary_unanswerable():
    llm = _VerifierLLM(
        '{"verdict":"no","evidence_quote":'
        '"The method requires no fine-tuning and is a drop-in replacement."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the method require fine-tuning?",
        evidence=("The method requires no fine-tuning and is a drop-in replacement."),
        candidate_answer="unanswerable",
    )

    assert result.answer == "no"
    assert result.trace["action"] == "recovered_boolean_from_abstention"
    assert result.trace["primary_answer"] == "unanswerable"
    assert result.trace["adjudicated_polarity"] == "no"
    assert result.trace["reason"] == "grounded_complete_relation"
    assert len(llm.calls) == 1


def test_qasper_boolean_question_allows_leading_discourse_marker():
    llm = _VerifierLLM(
        '{"verdict":"yes","evidence_quote":'
        '"Parallel data improves semantic role induction across languages."}'
    )

    result = verify_qasper_answerability(
        llm,
        question=(
            "Overall, does having parallel data improve semantic role induction "
            "across multiple languages?"
        ),
        evidence=("Parallel data improves semantic role induction across languages."),
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["action"] == "recovered_boolean_from_abstention"
    assert len(llm.calls) == 1


def test_qasper_boolean_relation_does_not_equate_created_with_experimented():
    llm = _VerifierLLM(
        '{"verdict":"yes","evidence_quote":'
        '"We recorded and preprocessed ZuCo 2.0, a new dataset."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did they experiment with the new dataset?",
        evidence="We recorded and preprocessed ZuCo 2.0, a new dataset.",
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["quote_supports_relation"] == "false"
    assert result.trace["raw_verifier_verdict"] == "yes"
    assert result.trace["reason"] == "grounded_quote_incomplete_relation"


def test_qasper_boolean_partial_quality_control_does_not_answer_quality_validation():
    llm = _VerifierLLM(
        '{"verdict":"yes_partial","evidence_quote":'
        '"We systematically controlled the experimental data collection process."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors validate the quality of the collected data?",
        evidence=(
            "We systematically controlled the experimental data collection "
            "process. The quality of the resulting data is harder to validate."
        ),
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["raw_verifier_verdict"] == "yes_partial"
    assert result.trace["reason"] == "grounded_partial_proposition"


def test_qasper_boolean_complete_downside_statement_answers_question():
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":'
        '"Lemmatizing is not a silver bullet and can remove useful distinctions."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Is there a downside to lemmatizing the training data?",
        evidence=(
            "Lemmatizing is not a silver bullet and can remove useful distinctions."
        ),
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["verdict"] == "yes"
    assert result.trace["raw_verifier_verdict"] == "yes_complete"
    assert result.trace["reason"] == "grounded_complete_proposition"


def test_qasper_complete_verdict_accepts_grounded_semantic_paraphrase():
    quote = "Each answer was labeled independently by two annotators."
    llm = _VerifierLLM('{"verdict":"yes_complete","evidence_quote":' f'"{quote}"}}')

    result = verify_qasper_answerability(
        llm,
        question="Are the answers double annotated?",
        evidence=quote,
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["verdict"] == "yes"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert "Modal relations are strict" not in llm.calls[0][0]


def test_qasper_complete_verdict_still_requires_question_relation():
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":'
        '"The method can be used as a drop-in component without fine-tuning."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Is fine-tuning required to use the method?",
        evidence=("The method can be used as a drop-in component without fine-tuning."),
        candidate_answer="no",
    )

    assert result.answer == "no"
    assert result.trace["verdict"] == "no"
    assert result.trace["raw_verifier_verdict"] == "yes_complete"
    assert result.trace["quote_grounded"] == "true"
    assert result.trace["quote_supports_relation"] == "true"
    assert result.trace["reason"] == "grounded_complete_proposition"
    assert result.trace["action"] == "confirmed_candidate"
    assert "Modal relations are strict" in llm.calls[0][0]


def test_qasper_complete_verdict_rejects_topical_quote_without_action_relation():
    quote = "Interdisciplinary insights are essential for this research area."
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":'
        '"Interdisciplinary insights are essential for this research area."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Do they demonstrate why interdisciplinary insights are important?",
        evidence=quote,
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["quote_grounded"] == "false"
    assert result.trace["quote_supports_relation"] == "false"
    assert result.trace["reason"] == "grounded_quote_incomplete_relation"


def test_qasper_answerability_rejects_boolean_candidate_when_question_is_unresolved():
    llm = _VerifierLLM('{"verdict":"insufficient_evidence","evidence_quote":""}')

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the training data?",
        evidence=(
            "The paper reports model accuracy and names the evaluation datasets, "
            "but does not discuss releasing training data."
        ),
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["status"] == "ok"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "abstained_insufficient_evidence"


def test_qasper_answerability_repairs_only_invalid_json_structure_once():
    llm = _VerifierLLM(
        [
            (
                "```json\n"
                '{"verdict":"unsupported","evidence_quote":""}\n'
                "trailing prose"
            ),
            '{"verdict":"unsupported","evidence_quote":""}',
        ]
    )

    result = verify_qasper_answerability(
        llm,
        question="What algorithm creates the embeddings?",
        evidence="The paper does not state how the embeddings are created.",
        candidate_answer="SGNS",
    )

    assert result.answer == "unanswerable"
    assert result.trace["status"] == "ok"
    assert result.trace["repair_attempted"] == "true"
    assert result.trace["repair_status"] == "ok"
    assert result.trace["initial_response"].startswith("```json")
    assert len(llm.calls) == 2
    assert "Do not reconsider the evidence" in llm.calls[1][0]
    assert all(call[1]["max_tokens"] >= 128 for call in llm.calls)
    assert all(
        call[1]["response_format"]["json_schema"]["schema"]["properties"][
            "evidence_quote"
        ]["maxLength"]
        <= 640
        for call in llm.calls
    )
    assert "at most 20 words" in llm.calls[0][0]


def test_qasper_answerability_does_not_repair_response_without_verdict():
    llm = _VerifierLLM("not json")

    result = verify_qasper_answerability(
        llm,
        question="What algorithm creates the embeddings?",
        evidence="The paper discusses embeddings.",
        candidate_answer="SGNS",
    )

    assert result.answer == "SGNS"
    assert result.trace["status"] == "error"
    assert result.trace["repair_attempted"] == "false"
    assert result.trace["repair_status"] == "not_repairable"
    assert result.trace["initial_response"] == "not json"
    assert len(llm.calls) == 1


def test_qasper_boolean_verifier_requires_quote_to_support_question_relation():
    llm = _VerifierLLM(
        '{"verdict":"yes","evidence_quote":'
        '"The paper reports model accuracy on three public benchmarks."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the training data?",
        evidence=(
            "The paper reports model accuracy on three public benchmarks. "
            "It does not discuss access to training data."
        ),
        candidate_answer="yes",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "abstained_insufficient_evidence"
    assert result.trace["quote_grounded"] == "false"
    assert result.trace["quote_supports_relation"] == "false"
