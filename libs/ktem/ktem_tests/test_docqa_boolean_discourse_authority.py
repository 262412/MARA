from __future__ import annotations

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


def _evidence(text: str) -> dict[str, str]:
    return {
        "evidence_id": "anonymous-result",
        "source_id": "paper",
        "section_id": "experiments",
        "text": text,
    }


def _run(question: str, text: str, generated_answer: str = "yes"):
    return execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="boolean",
            verification_mode="strict",
            verification_domain="qasper",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": [_evidence(text)]},
        generate=lambda *_args: generated_answer,
    )


def test_overall_discourse_conclusion_controls_small_improvement_polarity() -> None:
    question = (
        "Overall, does auxiliary supervision improve multilingual argument "
        "induction?"
    )
    decisive = (
        "These results indicate that little information about argument structure "
        "can be learned from the auxiliary supervision."
    )
    result = _run(
        question,
        (
            "Our multilingual model uses auxiliary supervision for argument "
            "induction. The model obtains small improvements in both languages. "
            f"{decisive}"
        ),
    )

    assert result.answer == "no"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "no"
    assert result.verify_decision.semantic_correction_applied is True
    assert decisive in result.verify_decision.authoritative_quote
    [span] = result.verify_decision.claim_results[0]["supporting_evidence_spans"]
    assert span["qualifier"] == "limited_information"


def test_background_task_claim_cannot_supply_current_experiment_authority() -> None:
    result = _run(
        "Do the authors experiment with other tasks?",
        (
            "A prior encoder was reported to work across various NLP tasks. "
            "For our experiments, we use an adapted encoder for entity labeling."
        ),
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.canonical_answer_polarity == ""
    assert result.guardrail_decision.action == "abstain"


def test_explicit_current_experiment_closure_can_authorize_no() -> None:
    current_scope = (
        "For our experiments, we evaluate the adapted encoder only on entity "
        "labeling and report only entity-labeling results."
    )
    result = _run(
        "Do the authors experiment with other tasks?",
        (
            "A prior encoder was reported to work across various NLP tasks. "
            f"{current_scope}"
        ),
        generated_answer="no",
    )

    assert result.answer == "no"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "no"
    assert current_scope in result.verify_decision.authoritative_quote
    assert "prior encoder" not in result.verify_decision.authoritative_quote.lower()
