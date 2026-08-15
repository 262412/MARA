from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.typed_retrieval_recovery import (
    typed_qasper_initial_query,
    verifier_recovery_query,
)


INDEXING_QUESTION = (
    "Do they employ their indexing-based method to create a sample of a QA "
    "Wikipedia dataset?"
)
PARALLEL_QUESTION = (
    "Overall, does having parallel data improve semantic role induction "
    "across multiple languages?"
)


def _item(
    evidence_id: str,
    text: str,
    *,
    section_id: str = "methods",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section_id,
        "text": text,
    }


def _boolean_request(question: str, *, route_policy: str = "doc") -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=["doc_text", "hybrid"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def test_direct_indexing_abstract_has_exact_yes_authority_and_citation() -> None:
    item = _item(
        "direct-abstract",
        (
            "We present an indexing-based method for the creation of a "
            "silver-standard answer-retrieval dataset using the entire Wikipedia."
        ),
    )

    authority = boolean_claim_authority(INDEXING_QUESTION, "yes", [item])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == identity_of(item).key
    assert support.evidence_ref == support.span_id
    assert support.quote == item["text"]
    assert support.actor == "current_paper"
    assert support.relation in {"create", "use"}
    assert {"dataset", "indexing", "method", "wikipedia"} <= set(
        support.object.split()
    )


def test_adjacent_methods_atoms_form_strict_bounded_authority() -> None:
    item = _item(
        "distributed-methods",
        (
            "We index Wikipedia paragraphs with Lucene as our indexing-based "
            "method. We use this method to create a silver-standard "
            "answer-retrieval dataset."
        ),
    )
    plan = build_query_plan(
        INDEXING_QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )

    bound = bind_evidence_slots(plan, [item])
    authority = boolean_claim_authority(INDEXING_QUESTION, "yes", [item])

    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(item).key,)
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == identity_of(item).key
    assert support.evidence_ref == support.span_id
    assert "indexing-based method" in support.quote
    assert "answer-retrieval dataset" in support.quote


@pytest.mark.parametrize(
    "text,section_id",
    (
        (
            "We index Wikipedia paragraphs with Lucene. We create an unrelated "
            "image-caption dataset for a separate experiment.",
            "methods",
        ),
        (
            "Prior work indexed Wikipedia with Lucene and used this method to "
            "create an answer-retrieval dataset.",
            "related_work",
        ),
        (
            "We index Wikipedia with Lucene and Terrier. We use this method to "
            "create a news dataset, and use that method to create a QA dataset.",
            "methods",
        ),
        (
            "We plan to index Wikipedia with Lucene. Future work will use this "
            "method to create an answer-retrieval dataset.",
            "future_work",
        ),
        (
            "Wikipedia motivates our introduction. We use this method to create "
            "an answer-retrieval dataset from a private news archive.",
            "methods",
        ),
    ),
)
def test_distributed_indexing_near_matches_do_not_become_authority(
    text: str,
    section_id: str,
) -> None:
    plan = build_query_plan(
        INDEXING_QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )

    item = _item("near-match", text, section_id=section_id)
    bound = bind_evidence_slots(plan, [item])
    authority = boolean_claim_authority(INDEXING_QUESTION, "yes", [item])

    [slot] = bound.evidence_slots
    assert slot.status in {"missing", "retrieved_unverified"}
    assert slot.status != "verified_support"
    assert authority is not None
    assert authority.status != "supported"


def test_typed_queries_keep_one_original_question_and_one_focused_frame() -> None:
    request = _boolean_request(INDEXING_QUESTION)

    focused = verifier_recovery_query(request)
    initial = typed_qasper_initial_query(request, INDEXING_QUESTION)

    assert focused.count(INDEXING_QUESTION) == 0
    assert initial.count(INDEXING_QUESTION) == 1
    assert "actor:current_paper" in focused
    assert "predicate:use" in focused
    assert "object:dataset indexing method wikipedia" in focused
    assert "indexing" in focused
    assert "dataset" in focused
    assert "wikipedia" in focused


def _parallel_candidates() -> list[dict[str, Any]]:
    return [
        _item(
            "parallel-abstract",
            (
                "We propose a Bayesian model of semantic role induction in "
                "multiple languages and use it to study parallel corpora. "
                "Our joint model captures role alignments across languages. "
                "We evaluate the same model in several training scenarios. "
                "We compare monolingual training with a parallel corpus. "
                "Adding word alignments in parallel sentences results in small, "
                "non-significant improvements in both languages."
            ),
            section_id="results",
        ),
        _item(
            "multilingual-model",
            "The multilingual model couples aligned role variables.",
        ),
        _item(
            "baseline",
            "The baseline assigns roles from syntactic functions.",
        ),
        _item(
            "conclusion",
            (
                "Increasing monolingual unlabeled data improves German results. "
                "Adding word alignments in parallel sentences gives small, "
                "non-significant improvements."
            ),
            section_id="conclusions",
        ),
    ]


def test_four_parallel_candidates_form_bounded_exact_negative_authority() -> None:
    items = _parallel_candidates()
    identities_before = [identity_of(item).key for item in items]
    plan = build_query_plan(
        PARALLEL_QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )

    bound = bind_evidence_slots(plan, items)
    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.status != "verified_support"

    authority = boolean_claim_authority(
        PARALLEL_QUESTION,
        "Overall, no. The gains are not significant.",
        items,
    )

    assert [identity_of(item).key for item in items] == identities_before
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    [support] = authority.supporting
    assert support.evidence_id == identity_of(items[0]).key
    assert support.evidence_ref == support.span_id
    assert support.actor == "current_paper"
    assert support.qualifier in {"small", "non_significant"}
    assert "semantic role induction" in support.quote.lower()
    assert "parallel" in support.quote.lower()
    assert "small" in support.quote.lower()


@pytest.mark.parametrize(
    "question,text,section_id",
    (
        (
            PARALLEL_QUESTION,
            "The parallel model gives improvements in several experiments.",
            "results",
        ),
        (
            PARALLEL_QUESTION,
            (
                "Parallel data improves semantic role induction in English, but "
                "does not improve it in German."
            ),
            "results",
        ),
        (
            PARALLEL_QUESTION,
            (
                "Increasing monolingual data significantly improves semantic "
                "role induction. Parallel alignments are described separately."
            ),
            "results",
        ),
        (
            PARALLEL_QUESTION,
            (
                "Previous work found that parallel data gives non-significant "
                "improvements for semantic role induction across languages."
            ),
            "related_work",
        ),
        (
            PARALLEL_QUESTION,
            (
                "One setting shows significant gains from parallel data for "
                "semantic role induction, while another reports no gain."
            ),
            "results",
        ),
    ),
)
def test_parallel_near_matches_do_not_authorize_a_unique_no(
    question: str,
    text: str,
    section_id: str,
) -> None:
    authority = boolean_claim_authority(
        question,
        "no",
        [_item("parallel-near-match", text, section_id=section_id)],
    )

    assert authority is not None
    assert not (
        authority.status == "supported"
        and authority.canonical_answer_polarity == "no"
    )


@pytest.mark.parametrize("route_policy", ("doc", "auto", "hybrid"))
def test_domain_comparison_positive_keeps_exact_authority_without_recovery(
    route_policy: str,
) -> None:
    question = "Is the student reflection data very different from the newspaper data?"
    item = _item(
        "domain-performance",
        (
            "Evaluations demonstrated that summaries produced by the tuned model "
            "achieved higher ROUGE scores compared to a model trained on just "
            "student reflection data or just newspaper data. The tuned model "
            "also achieved higher scores compared to extractive summarization "
            "baselines, and was judged more coherent and readable. Second, we "
            "explored whether synthesizing summaries of student data could boost "
            "performance. We proposed a template-based model to synthesize new "
            "data, which further increased ROUGE scores."
        ),
        section_id="results",
    )

    result = execute_controller_turn(
        _boolean_request(question, route_policy=route_policy),
        retrieve=lambda *_args: {"evidence": [item]},
        generate=lambda *_args: "yes",
    )

    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "yes"
    assert result.verify_decision.authoritative_evidence_id == identity_of(item).key
    assert result.verify_decision.authoritative_quote
    assert result.verify_decision.verified_citations == [identity_of(item).key]
    assert not [
        event
        for event in result.controller_trace
        if event.get("verifier_recovery_attempt")
        or event.get("stage") == "route_switch"
    ]
