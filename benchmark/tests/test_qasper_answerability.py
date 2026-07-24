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


def test_qasper_answerability_does_not_let_secondary_verifier_flip_candidate():
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

    assert result.answer == "yes"
    assert result.trace["verdict"] == "no"
    assert result.trace["action"] == "preserved_conflicting_candidate"
    assert "CANDIDATE ANSWER" not in llm.calls[0][0]


def test_qasper_answerability_preserves_no_candidate_on_conflicting_yes_verdict():
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

    assert result.answer == "no"
    assert result.trace["verdict"] == "yes"
    assert result.trace["action"] == "preserved_conflicting_candidate"


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
