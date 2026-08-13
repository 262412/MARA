from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn

QUESTION = "How many participants did the authors recruit for the study?"
ANSWER = "The authors recruited 42 participants."
TOPIC_ONLY = "The study discusses participant demographics and recruitment methods."
EXACT_RELATION = "We recruited 42 participants for the study."


def _evidence(evidence_id: str, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
        **extra,
    }


def _request(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    *,
    question: str = QUESTION,
) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=allowed_routes,
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode", "recovery_route"),
    (
        ("doc", ["doc_text"], None, "doc_text"),
        ("auto", ["doc_text", "hybrid"], None, "hybrid"),
        ("auto", ["doc_text", "hybrid"], "thorough", "doc_text"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_answer_relation_recovery_commits_same_authority_across_routes(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    recovery_route: str,
) -> None:
    calls: list[tuple[str, int]] = []
    authoritative = _evidence("authoritative", EXACT_RELATION)
    authoritative_id = identity_of(authoritative).key

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        evidence = (
            [_evidence("topic-only", TOPIC_ONLY)]
            if request.retrieval_round_id == 1
            else [authoritative]
        )
        return {"evidence": evidence}

    result = execute_controller_turn(
        _request(route_policy, allowed_routes, agent_mode),
        retrieve=retrieve,
        generate=lambda *_args: ANSWER,
    )

    assert calls == [("doc_text", 1), (recovery_route, 2)]
    assert result.answer == ANSWER
    assert result.engine_terminal_answer == ANSWER
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.authoritative_evidence_id == authoritative_id
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.typed_authority["verified_slot_ids"] == [
        "support:answer_relation"
    ]
    [atom] = result.verify_decision.typed_authority["authority_atoms"]
    assert atom["evidence_id"] == authoritative_id
    assert atom["quote"] == EXACT_RELATION
    assert atom["quantifier"] == "42"
    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_support"
    assert slot["evidence_ids"] == [authoritative_id]
    assert result.engine_terminal_state["typed_authority"] == (
        result.verify_decision.typed_authority
    )
    terminal_events = [
        event
        for event in result.controller_trace
        if event.get("stop_reason") == "authority_recovered"
    ]
    assert len(terminal_events) == 1
    assert terminal_events[0]["authority_changed"] is True
    assert terminal_events[0]["retry_reason"] == (
        "required_answer_relation_authority_missing"
    )
    if agent_mode == "thorough":
        recovery = [
            event
            for event in result.controller_trace
            if event.get("verifier_recovery_attempt") == 1
        ]
        assert [event["stage"] for event in recovery] == [
            "critic",
            "focused_retrieval",
            "evidence_rebind",
            "reverify",
        ]
        assert all(event["agent_mode"] == "thorough" for event in recovery)


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode"),
    (
        ("doc", ["doc_text"], None),
        ("auto", ["doc_text", "hybrid"], None),
        ("auto", ["doc_text", "hybrid"], "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_complete_answer_relation_does_not_retry(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
) -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [_evidence("authoritative", EXACT_RELATION)]}

    result = execute_controller_turn(
        _request(route_policy, allowed_routes, agent_mode),
        retrieve=retrieve,
        generate=lambda *_args: ANSWER,
    )

    assert calls == [("doc_text", 1)]
    assert result.verify_decision.status == "supported"
    assert not any(
        event.get("verifier_recovery_attempt") for event in result.controller_trace
    )


_NEGATIVE_CASES = (
    (
        "topic_only",
        "How many participants did the authors recruit for the study?",
        "The study discusses participant recruitment methods.",
        _evidence(
            "topic-only",
            "The study discusses participant demographics and recruitment methods.",
        ),
    ),
    (
        "wrong_actor_scope",
        "How did the authors train the model?",
        "The authors used contrastive learning.",
        _evidence(
            "cited-work",
            "Prior work used contrastive learning to train the model.",
            section_id="related_work",
        ),
    ),
    (
        "qualifier_missing",
        "Which component did the authors use only during decoding?",
        "They used the reranker only during decoding.",
        _evidence(
            "qualifier-missing",
            "We used the reranker during decoding.",
        ),
    ),
    (
        "relation_missing",
        "How did the authors improve recall?",
        "They improved recall with graph expansion.",
        _evidence("relation-missing", "We improved recall."),
    ),
    (
        "title_only",
        "What mechanism did the authors use for retrieval?",
        "They used a graph encoder.",
        _evidence(
            "title-only",
            "Graph Encoder",
            element_type="title",
        ),
    ),
)


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode"),
    (
        ("doc", ["doc_text"], None),
        ("auto", ["doc_text", "hybrid"], None),
        ("auto", ["doc_text", "hybrid"], "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
@pytest.mark.parametrize(
    ("_case_id", "question", "answer", "evidence"),
    _NEGATIVE_CASES,
    ids=[case[0] for case in _NEGATIVE_CASES],
)
def test_incomplete_answer_relation_stays_safe_across_routes(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
    _case_id: str,
    question: str,
    answer: str,
    evidence: dict[str, Any],
) -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {"evidence": [evidence]}

    result = execute_controller_turn(
        _request(
            route_policy,
            allowed_routes,
            agent_mode,
            question=question,
        ),
        retrieve=retrieve,
        generate=lambda *_args: answer,
    )

    assert len(calls) == 2
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.verified_citations == []
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.typed_authority["authority_atoms"] == []
    recovery = [
        event
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt") == 1
    ]
    assert recovery
    assert all(
        event["retry_reason"] == "required_answer_relation_authority_missing"
        for event in recovery
    )
    focused = [
        event
        for event in recovery
        if event.get("stage") in {"focused_retrieval", "route_switch"}
    ]
    assert len(focused) == 1
    assert " polarity " not in f" {focused[0]['focused_query'].lower()} "
    assert not any(
        event.get("stop_reason") == "authority_recovered"
        for event in result.controller_trace
    )
