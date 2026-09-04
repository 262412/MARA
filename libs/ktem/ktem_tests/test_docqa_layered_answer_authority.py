from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision


def _request(
    question: str,
    *,
    domain: str,
    task_type: str = "free_text",
    route_policy: str = "doc",
    allowed_routes: list[str] | None = None,
    agent_mode: str | None = None,
) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type=task_type,
        verification_mode="strict",
        verification_domain=domain,
        route_policy=route_policy,
        allowed_routes=allowed_routes or ["doc_text"],
        agent_mode=agent_mode,
        selected_file_ids=["source"],
        origin="benchmark",
    )


def _item(text: str, *, evidence_id: str = "authority") -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "source",
        "section_id": "method",
        "text": text,
    }


def _run(
    question: str,
    answer: str,
    evidence: list[dict[str, Any]],
    *,
    domain: str = "qasper",
    task_type: str = "free_text",
    route_policy: str = "doc",
    allowed_routes: list[str] | None = None,
    agent_mode: str | None = None,
) -> Any:
    return execute_controller_turn(
        _request(
            question,
            domain=domain,
            task_type=task_type,
            route_policy=route_policy,
            allowed_routes=allowed_routes,
            agent_mode=agent_mode,
        ),
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: answer,
    )


def test_qasper_supported_paraphrase_is_bound_at_runtime() -> None:
    question = "What background knowledge do they leverage?"
    evidence = [_item("The method leverages labeled features as prior knowledge.")]

    result = _run(question, "The method uses labeled features.", evidence)

    assert result.engine_terminal_answer == "The method uses labeled features."
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    [claim] = result.verify_decision.claim_results
    assert claim["authority_status"] == "semantic"
    assert claim["object"] == "labeled features"


def test_qasper_supported_multi_sentence_extension_is_retained() -> None:
    question = "What background knowledge do they leverage?"
    evidence = [
        _item(
            "The method leverages labeled features as prior knowledge. "
            "It also leverages the maximum entropy principle as prior knowledge."
        )
    ]
    answer = (
        "The method uses labeled features. "
        "It also relies on the maximum entropy principle."
    )

    result = _run(question, answer, evidence)

    assert "labeled features" in result.engine_terminal_answer
    assert "maximum entropy principle" in result.engine_terminal_answer
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.verify_decision.unknown_claims == []
    assert [claim["status"] for claim in result.verify_decision.claim_results] == [
        "supported",
        "supported",
    ]
    assert not any(
        event.get("stage") == "claim_level_revision"
        for event in result.controller_trace
    )


def test_qasper_supported_explanatory_extension_is_retained_without_relation_repeat() -> (
    None
):
    question = "What background knowledge do they leverage?"
    evidence = [
        _item(
            "The method leverages labeled features as prior knowledge. "
            "Labeled features are manually provided indicators of specific classes."
        )
    ]
    answer = (
        "The method uses labeled features. "
        "Labeled features are manually provided indicators of specific classes."
    )

    result = _run(question, answer, evidence)

    assert result.engine_terminal_answer == answer.replace(". ", ".\n")
    assert result.verify_decision.status == "supported"
    assert [
        claim["authority_status"] for claim in result.verify_decision.claim_results
    ] == [
        "semantic",
        "semantic",
    ]


def test_qasper_unsupported_extension_is_removed_and_reverified() -> None:
    question = "What is novel about their document-level encoder?"
    evidence = [_item("We propose a novel document-level encoder based on BERT.")]
    answer = "It is based on BERT. The paper uses an unsupported private ontology."

    result = _run(question, answer, evidence)

    assert result.engine_terminal_answer == "It is based on BERT."
    assert "private ontology" not in result.engine_terminal_answer
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert any(
        event.get("stage") == "claim_level_revision"
        for event in result.controller_trace
    )


def test_qasper_contradictory_extension_remains_fail_closed() -> None:
    question = "What is novel about their document-level encoder?"
    evidence = [
        _item(
            "We propose a novel document-level encoder based on BERT.",
            evidence_id="yes",
        ),
        _item(
            "The document-level encoder is not based on transformer architecture.",
            evidence_id="no",
        ),
    ]
    answer = (
        "It is based on BERT. "
        "The document-level encoder is based on transformer architecture."
    )

    result = _run(question, answer, evidence)

    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.verified_citations == []


@pytest.mark.parametrize(
    ("route_policy", "agent_mode", "candidate"),
    (
        (
            "doc",
            None,
            "KAR is an end-to-end MRC model named Knowledge Aided Reader.",
        ),
        (
            "auto",
            None,
            r"Answer: $$\text{KAR is an end-to-end MRC model named Knowledge Aided Reader.}$$",
        ),
        (
            "auto",
            "thorough",
            "Answer(KAR is an end-to-end MRC model named Knowledge Aided Reader.)",
        ),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_qasper_controller_candidate_normalization_binds_kar_authority(
    route_policy: str,
    agent_mode: str | None,
    candidate: str,
) -> None:
    question = "What type of model is KAR?"
    evidence = [
        _item(
            "We propose an end-to-end MRC model named as Knowledge Aided Reader (KAR).",
            evidence_id="1809.03449-abstract",
        )
    ]
    result = _run(
        question,
        candidate,
        evidence,
        route_policy=route_policy,
        allowed_routes=["doc_text", "hybrid"],
        agent_mode=agent_mode,
    )

    normalized = "KAR is an end-to-end MRC model named Knowledge Aided Reader."
    assert result.answer == normalized
    assert result.engine_terminal_answer == normalized
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.typed_authority["candidate_answer"] == normalized
    assert result.verify_decision.typed_authority["authority_atoms"][0][
        "predicate"
    ] == ("define")


def test_qasper_unsupported_wrapped_controller_candidate_remains_abstention() -> None:
    result = _run(
        "What type of model is KAR?",
        r"Answer: $$\text{KAR is a graph neural network.}$$",
        [
            _item(
                "We propose an end-to-end MRC model named as Knowledge Aided Reader (KAR).",
                evidence_id="1809.03449-abstract",
            )
        ],
        route_policy="auto",
        allowed_routes=["doc_text", "hybrid"],
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.action == "abstain"
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.typed_authority["authority_atoms"] == []


def test_finance_explanatory_boolean_answer_is_not_rejected_by_qasper_gate() -> None:
    question = "Did AMD report customer concentration in FY22?"
    item = _item(
        "One customer accounted for 16% of our consolidated net revenue for the "
        "year ended December 31, 2022."
    )
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="extractive",
            verification_domain="finance",
        ),
        [item],
    )
    request = _request(question, domain="finance", task_type="extractive")
    request.query_plan = plan
    answer = (
        "Yes, one customer accounted for 16% of our consolidated net revenue "
        "for the year ended December 31, 2022."
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="text_rag", items=[item], metadata={}),
        answer,
    )

    assert decision.status == "supported"
    assert decision.verified_citations == [identity_of(item).key]
    assert decision.typed_authority == {}
    assert decision.claim_results[0]["status"] == "supported"


@pytest.mark.parametrize(
    ("domain", "question", "answer", "evidence"),
    (
        (
            "alce",
            "What is the main benefit of the method?",
            "The approach is more robust to noise.",
            "The method improves robustness to noise.",
        ),
        (
            "finance",
            "What drove the reduction in SG&A expense as a percent of net sales in FY2023?",
            "The decrease was caused by lower compensation and benefits.",
            "SG&A expenses as a percentage of net sales decreased in FY2023 "
            "primarily due to lower compensation and benefits.",
        ),
    ),
    ids=("alce", "finance"),
)
def test_cross_dataset_runtime_accepts_supported_paraphrase(
    domain: str,
    question: str,
    answer: str,
    evidence: str,
) -> None:
    result = _run(question, answer, [_item(evidence)], domain=domain)

    assert result.engine_terminal_answer == answer
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.verify_decision.verified_citations


def test_cross_dataset_runtime_retains_supported_multi_sentence_extension() -> None:
    question = "What is the main benefit of the method?"
    answer = "The approach is more robust to noise. It also lowers annotation cost."
    evidence = [
        _item("The method improves robustness to noise. It reduces annotation cost.")
    ]

    result = _run(question, answer, evidence, domain="alce")

    assert result.engine_terminal_answer == answer.replace(". ", ".\n")
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.verify_decision.unknown_claims == []


def test_cross_dataset_runtime_removes_unconfirmed_extension_and_reverifies() -> None:
    question = "What is the main benefit of the method?"
    answer = "The approach is more robust to noise. It was invented on Mars."
    evidence = [_item("The method improves robustness to noise.")]

    result = _run(question, answer, evidence, domain="alce")

    assert result.engine_terminal_answer == "The approach is more robust to noise."
    assert result.verify_decision.status == "supported"
    assert any(
        event.get("stage") == "claim_level_revision"
        for event in result.controller_trace
    )


def test_cross_dataset_runtime_rejects_contradictory_extension() -> None:
    question = "What is the main benefit of the method?"
    answer = "The approach is more robust to noise. The method is not robust to noise."
    evidence = [
        _item("The method improves robustness to noise.", evidence_id="support"),
        _item("The method is not robust to noise.", evidence_id="contradiction"),
    ]

    result = _run(question, answer, evidence, domain="alce")

    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.action == "abstain"
