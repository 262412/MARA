from __future__ import annotations

from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_evidence_scope import resolve_closed_scope_boolean
from ktem.docqa.boolean_proposition_candidates import (
    boolean_proposition_candidate_score,
)
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_evidence_score
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_planning import build_query_plan

QUESTION = "Do they analyze specific derogatory words?"
POSITIVE_TEXT = (
    "A primary focus of this study is comparing different LGBTQ labels, "
    "specifically gay and homosexual. Respondents describe homosexual as "
    "outdated and derogatory."
)


def _item(
    evidence_id: str,
    text: str,
    *,
    section_id: str = "methods",
    page_label: str = "1",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "document_id": "paper",
        "page_label": page_label,
        "section_id": section_id,
        "text": text,
    }


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _assert_not_positive_authority(item: dict[str, Any]) -> None:
    assert resolve_closed_scope_boolean(QUESTION, [item]) is None
    assert boolean_proposition_candidate_score(QUESTION, item) == 0.0
    assert boolean_proposition_evidence_score(QUESTION, item) == 0.0
    authority = boolean_claim_authority(
        QUESTION,
        "unanswerable",
        [item],
        allow_missing_polarity=True,
    )
    assert authority is not None
    assert not (
        authority.status == "supported" and authority.canonical_answer_polarity == "yes"
    )


def test_selection_binding_and_verifier_share_structured_boolean_authority() -> None:
    item = _item("current-study", POSITIVE_TEXT)
    evidence_id = identity_of(item).key
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )

    assert boolean_proposition_candidate_score(QUESTION, item) > 0.0
    assert boolean_proposition_evidence_score(QUESTION, item) > 0.0

    bound = bind_evidence_slots(plan, [item])
    [slot] = bound.evidence_slots
    assert slot.evidence_ids == (evidence_id,)
    assert slot.status == "retrieved_unverified"

    authority = boolean_claim_authority(
        QUESTION,
        "unanswerable",
        [item],
        allow_missing_polarity=True,
    )
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "yes"
    [support] = authority.supporting
    assert support.evidence_id == evidence_id
    assert support.quote in POSITIVE_TEXT
    assert support.actor == "current_paper"
    assert support.section_scope == "methods"
    assert support.reason == "explicit_current_derogatory_label_analysis"

    result = execute_controller_turn(
        _request(),
        retrieve=lambda *_args: {"evidence": [item]},
        generate=lambda *_args: "unanswerable",
    )
    assert result.answer == "yes"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.canonical_answer_polarity == "yes"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.typed_authority["slot_bindings"] == {
        "support:boolean_proposition": [evidence_id]
    }


def test_related_work_quote_cannot_become_current_study_authority() -> None:
    item = _item(
        "related-work",
        (
            "Smith et al. write: 'A primary focus of this study is comparing the "
            "labels nova and vetus. Respondents describe vetus as outdated and "
            "derogatory.'"
        ),
        section_id="related_work",
    )

    _assert_not_positive_authority(item)


def test_unrelated_sentences_cannot_be_stitched_into_boolean_authority() -> None:
    item = _item(
        "unrelated-stitch",
        (
            "A primary focus of this study is comparing user-interface labels. "
            "The experiments analyze navigation efficiency. Prior work calls a "
            "different word outdated and derogatory."
        ),
    )

    _assert_not_positive_authority(item)


def test_generic_topic_match_remains_insufficient_for_specific_words() -> None:
    item = _item(
        "generic-topic",
        "We analyze dehumanizing language in online communities.",
    )

    _assert_not_positive_authority(item)


def test_structured_support_and_exact_opposite_authority_fail_closed() -> None:
    positive = _item("positive", POSITIVE_TEXT, page_label="1")
    negative = _item(
        "negative",
        "We do not analyze specific derogatory words or labels in this study.",
        page_label="2",
    )

    authority = boolean_claim_authority(
        QUESTION,
        "unanswerable",
        [positive, negative],
        allow_missing_polarity=True,
    )

    assert authority is not None
    assert authority.status == "conflicting"
    assert authority.canonical_answer_polarity == ""
    assert authority.reason == "conflicting_exact_boolean_propositions"
    assert authority.authoritative_conflict is not None
    assert authority.authoritative_conflict["status"] == "verified_conflict"
    assert {
        value["polarity"]
        for side in ("positive_authorities", "negative_authorities")
        for value in authority.authoritative_conflict[side]
    } == {"yes", "no"}
