from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_binding_trace
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


@dataclass(frozen=True)
class VerifiedCase:
    question: str
    generated_answer: str
    evidence_text: str
    expected_answer: str
    relation: str
    object_terms: frozenset[str]
    evidence_polarity: str
    candidate_reason: str


def _evidence(
    evidence_id: str,
    text: str,
    *,
    section_id: str = "results",
    page_label: str = "1",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "page_label": page_label,
        "section_id": section_id,
        "text": text,
    }


def _run_boolean(
    question: str,
    generated_answer: str,
    items: list[dict[str, Any]],
):
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
        retrieve=lambda *_args: {"evidence": items},
        generate=lambda *_args: generated_answer,
    )


@pytest.mark.parametrize(
    "case",
    (
        VerifiedCase(
            question="Did the authors evaluate the model on clinical tasks?",
            generated_answer="yes",
            evidence_text="We evaluated the model on clinical tasks.",
            expected_answer="yes",
            relation="evaluate",
            object_terms=frozenset({"clinical", "model", "task"}),
            evidence_polarity="yes",
            candidate_reason="claim_scope_relation_and_polarity_compatible",
        ),
        VerifiedCase(
            question="Did the authors use the clinical corpus?",
            generated_answer="yes",
            evidence_text="We did not use the clinical corpus.",
            expected_answer="no",
            relation="use",
            object_terms=frozenset({"clinical", "corpu"}),
            evidence_polarity="no",
            candidate_reason="scope_valid_opposite_proposition",
        ),
    ),
)
def test_exact_boolean_transaction_records_the_complete_state(
    case: VerifiedCase,
) -> None:
    item = _evidence("authority", case.evidence_text)
    evidence_id = identity_of(item).key

    result = _run_boolean(
        case.question,
        case.generated_answer,
        [item],
    )

    assert result.retrieve_decision.status == "good"
    assert result.answer == case.expected_answer
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.action == "generate"
    assert result.guardrail_decision.action == "return"
    assert result.verify_decision.input_answer_polarity == "yes"
    assert result.verify_decision.canonical_answer_polarity == case.expected_answer
    assert result.verify_decision.semantic_correction_applied is (
        case.expected_answer == "no"
    )

    typed = result.verify_decision.typed_authority
    assert typed["state"] == "verified_support"
    assert typed["reason"] == "exact_boolean_proposition"
    assert typed["canonical_answer_polarity"] == case.expected_answer
    assert typed["required_slot_ids"] == ["support:boolean_proposition"]
    assert typed["verified_slot_ids"] == ["support:boolean_proposition"]
    assert typed["slot_bindings"] == {"support:boolean_proposition": [evidence_id]}

    [claim] = result.verify_decision.claim_results
    assert claim["actor"] == "current_paper"
    assert claim["relation"] == claim["predicate"] == case.relation
    assert case.object_terms <= set(claim["object"].split())
    assert claim["qualifier"] == "none"
    assert claim["scope"] == claim["section_scope"] == "results"
    assert claim["verified_slot_state"] == "verified_support"
    [span] = claim["supporting_evidence_spans"]
    assert span["evidence_id"] == evidence_id
    assert span["evidence_ref"] == span["span_id"]
    assert span["quote"] == case.evidence_text
    assert span["span_start"] == 0
    assert span["span_end"] == len(case.evidence_text)
    assert span["polarity"] == case.evidence_polarity
    assert span["reason"] == case.candidate_reason

    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_support"
    assert slot["evidence_ids"] == [evidence_id]

    binding = boolean_proposition_binding_trace(
        case.question,
        case.generated_answer,
        [item],
    )
    candidate = next(
        value
        for value in binding["proposition_candidates"]
        if value["span"] == case.evidence_text
    )
    assert candidate["actor"] == "current_paper"
    assert candidate["predicate"] == case.relation
    assert case.object_terms <= set(candidate["object"].split())
    assert candidate["qualifier"] == "none"
    assert candidate["scope"] == "results"
    assert candidate["polarity"] == case.evidence_polarity
    assert candidate["reason"] == case.candidate_reason

    commit = result.engine_terminal_commit
    assert commit["semantic_answer"] == case.expected_answer
    assert commit["answer_status"] == "answered"
    assert commit["citations"] == [evidence_id]
    assert [value["canonical_id"] for value in commit["authoritative_evidence"]] == [
        evidence_id
    ]


@pytest.mark.parametrize(
    ("evidence_text", "generated_answer"),
    (
        ("We employed the clinical corpus.", "yes"),
        ("The clinical corpus was used in our experiments.", "yes"),
        (
            "We selected the clinical corpus. It was then used for model evaluation.",
            "yes",
        ),
        ("We used the clinical corpus.", "unanswerable The evidence is unclear."),
    ),
)
def test_synonym_passive_cross_clause_and_generator_abstention_share_authority(
    evidence_text: str,
    generated_answer: str,
) -> None:
    question = "Did the authors use the clinical corpus?"
    item = _evidence("variant", evidence_text)
    evidence_id = identity_of(item).key

    result = _run_boolean(question, generated_answer, [item])

    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "yes"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.authoritative_evidence_id == evidence_id
    assert result.verify_decision.authoritative_quote in evidence_text
    assert result.guardrail_decision.action == "return"
    assert result.engine_terminal_commit["semantic_answer"] == "yes"
    assert result.engine_terminal_commit["answer_status"] == "answered"
    assert result.engine_terminal_commit["citations"] == [evidence_id]


@pytest.mark.parametrize(
    (
        "question",
        "evidence_text",
        "section_id",
        "expected_candidate_reason",
        "expected_authority_reason",
    ),
    (
        (
            "Did the authors evaluate the model on clinical tasks?",
            "Previous work evaluated the model on clinical tasks.",
            "related_work",
            "cited_work_does_not_establish_current_paper_claim",
            "retrieval_evidence_insufficient",
        ),
        (
            "Did the authors evaluate the model on clinical tasks?",
            "We evaluated the model on legal tasks.",
            "results",
            "claim_scope_relation_and_polarity_compatible",
            "exact_boolean_authority_missing",
        ),
        (
            "Did every language improve?",
            "English improved, but French was not reported.",
            "results",
            "claim_relation_or_object_incompatible",
            "retrieval_evidence_insufficient",
        ),
        (
            "Did the authors release source code?",
            "The source code section discusses release engineering terminology.",
            "results",
            "claim_scope_relation_and_polarity_compatible",
            "exact_boolean_authority_missing",
        ),
    ),
)
def test_scope_object_qualifier_and_topical_matches_remain_fail_closed(
    question: str,
    evidence_text: str,
    section_id: str,
    expected_candidate_reason: str,
    expected_authority_reason: str,
) -> None:
    item = _evidence("hard-negative", evidence_text, section_id=section_id)
    result = _run_boolean(question, "yes", [item])
    binding = boolean_proposition_binding_trace(question, "yes", [item])

    assert result.answer == ABSTAIN_MESSAGE
    assert result.guardrail_decision.action == "abstain"
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["answer_status"] == "abstained"
    assert result.engine_terminal_commit["citations"] == []
    assert result.verify_decision.canonical_answer_polarity == ""
    assert result.verify_decision.typed_authority.get("state", "missing") == "missing"
    assert result.verify_decision.typed_authority["reason"] == expected_authority_reason
    [slot] = (
        result.evidence_bundle.metadata.get("query_plan")
        or result.evidence_bundle.metadata["bound_query_plan"]
    )["evidence_slots"]
    assert slot["status"] in {"missing", "retrieved_unverified"}
    assert any(
        value["reason"] == expected_candidate_reason
        for value in binding["proposition_candidates"]
    )


def test_explicit_conflict_is_verified_but_terminally_abstained() -> None:
    question = "Did the authors use the clinical corpus?"
    positive = _evidence("positive", "We used the clinical corpus.", page_label="1")
    negative = _evidence(
        "negative",
        "We did not use the clinical corpus.",
        page_label="2",
    )
    expected_ids = {identity_of(positive).key, identity_of(negative).key}

    result = _run_boolean(question, "yes", [positive, negative])

    assert result.answer == "unanswerable"
    assert result.verify_decision.status == "verified_conflict"
    assert result.verify_decision.action == "abstain"
    assert result.guardrail_decision.action == "abstain"
    typed = result.verify_decision.typed_authority
    assert typed["state"] == "verified_conflict"
    assert typed["reason"] == "authoritative_conflict_abstention"
    assert {value["polarity"] for value in typed["authority_atoms"]} == {
        "yes",
        "no",
    }
    assert {value["evidence_id"] for value in typed["authority_atoms"]} == (
        expected_ids
    )
    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_conflict"
    assert set(slot["evidence_ids"]) == expected_ids
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["answer_status"] == "abstained"
    assert result.engine_terminal_commit["citations"] == []


def test_absence_never_becomes_negative_authority() -> None:
    question = "Did the authors use the clinical corpus?"
    item = _evidence(
        "topic-only",
        "The paper describes a clinical corpus and the model architecture.",
    )

    result = _run_boolean(question, "no", [item])

    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.canonical_answer_polarity == ""
    assert result.guardrail_decision.action == "abstain"
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["citations"] == []


def test_unchanged_evidence_and_slot_state_stop_without_reverification() -> None:
    question = "Did the authors conduct experiments on the dataset?"
    item = _evidence(
        "near-match",
        "The dataset provides experiments for evaluation.",
        section_id="experiments",
    )
    retrieval_calls = 0

    def retrieve(*_args: Any) -> dict[str, Any]:
        nonlocal retrieval_calls
        retrieval_calls += 1
        return {"evidence": [item]}

    result = execute_controller_turn(
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
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    terminal = next(
        value
        for value in reversed(result.controller_trace)
        if value.get("stage") == "evidence_rebind"
        and value.get("stop_reason") == "recovery_no_progress"
    )
    assert retrieval_calls == 2
    assert terminal["evidence_ids_before"] == terminal["evidence_ids_after"]
    assert terminal["slot_states_before"] == terminal["slot_states_after"]
    assert terminal["candidate_answer_before"] == terminal["candidate_answer_after"]
    assert terminal["slot_state_changed"] is False
    assert terminal["proposition_binding_changed"] is False
    assert terminal["candidate_changed"] is False
    assert terminal["authority_changed"] is False
    assert terminal["recovery_action"] == "stop_without_reverify"
    assert not any(
        value.get("stage") == "reverify" for value in result.controller_trace
    )
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["answer_status"] == "abstained"
