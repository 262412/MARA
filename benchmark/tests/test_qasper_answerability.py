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
    assert "determine the supported polarity" in llm.calls[0][0]
    assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True


def test_qasper_answerability_corrects_candidate_from_grounded_polarity():
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
    assert result.trace["action"] == "corrected_primary_polarity"
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
    assert result.trace["action"] == "corrected_primary_polarity"


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

    assert result.answer == "yes"
    assert result.trace["status"] == "ok"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "preserved_insufficient_candidate"


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
        <= 320
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

    assert result.answer == "yes"
    assert result.trace["verdict"] == "insufficient_evidence"
    assert result.trace["action"] == "preserved_insufficient_candidate"
    assert result.trace["quote_grounded"] == "true"
    assert result.trace["quote_supports_relation"] == "false"
