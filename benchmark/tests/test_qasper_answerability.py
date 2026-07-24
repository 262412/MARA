from types import SimpleNamespace
from typing import Any

from benchmark.qasper_answerability import verify_qasper_answerability


class _VerifierLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        return SimpleNamespace(text=self.response)


def test_qasper_answerability_rejects_related_but_unsupported_candidate():
    llm = _VerifierLLM('{"verdict":"unsupported"}')

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
    llm = _VerifierLLM('{"verdict":"supported"}')

    result = verify_qasper_answerability(
        llm,
        question="Which metric evaluates the system?",
        evidence="The system is evaluated using cosine similarity.",
        candidate_answer="cosine similarity",
    )

    assert result.answer == "cosine similarity"
    assert result.trace["verdict"] == "supported"


def test_qasper_answerability_does_not_rejudge_explicit_unanswerable():
    llm = _VerifierLLM('{"verdict":"supported"}')

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
    llm = _VerifierLLM('{"verdict":"no"}')

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


def test_qasper_answerability_corrects_boolean_candidate_polarity_from_evidence():
    llm = _VerifierLLM('{"verdict":"no"}')

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
    assert "CANDIDATE ANSWER" not in llm.calls[0][0]


def test_qasper_answerability_can_correct_no_candidate_to_yes():
    llm = _VerifierLLM('{"verdict":"yes"}')

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence="The authors released their source code with the paper.",
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["verdict"] == "yes"


def test_qasper_answerability_rejects_boolean_candidate_when_question_is_unresolved():
    llm = _VerifierLLM('{"verdict":"insufficient_evidence"}')

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
