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
BACKGROUND_CURRENT_STUDY = (
    "## Background ::: Attitudes Towards the Target Community\n\n"
    "Earlier surveys measured public attitudes toward the community BIBREF2. "
    "A separate research center reported similar trends BIBREF51.\n\n"
    "In addition to the public's overall attitudes, it is important to consider "
    "variation and change in the specific words used to refer to the community. "
    "Because these labels potentially convey different social meanings, a primary "
    "focus of this study involves comparing different labels, specifically nova "
    "and vetus. An external survey used vetus until 2008, but later changed its "
    "wording. This was likely because many people find the word vetus to be "
    "outdated and derogatory. A monitoring organization discusses the label's "
    "history BIBREF52."
)


def _item(
    evidence_id: str,
    text: str,
    *,
    section_id: str = "",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "document_id": "paper",
        "page_label": "1",
        "section_id": section_id,
        "text": text,
        "metadata": {"section_id": section_id},
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


def _assert_no_positive_authority(item: dict[str, Any]) -> None:
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


def test_background_current_study_proposition_is_shared_by_all_consumers() -> None:
    item = _item("background-current-study", BACKGROUND_CURRENT_STUDY)
    evidence_id = identity_of(item).key

    resolution = resolve_closed_scope_boolean(QUESTION, [item])
    assert resolution is not None
    assert resolution.polarity == "yes"
    assert resolution.decision.actor == "current_paper"
    assert resolution.decision.section_role == "methods"
    assert "a primary focus of this study" in resolution.evidence_quote
    assert "vetus to be outdated and derogatory" in resolution.evidence_quote

    assert boolean_proposition_candidate_score(QUESTION, item) > 0.0
    assert boolean_proposition_evidence_score(QUESTION, item) > 0.0

    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
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
    assert support.actor == "current_paper"
    assert support.section_scope == "methods"
    assert support.quote == resolution.evidence_quote

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


def test_attributed_study_in_background_remains_cited_work() -> None:
    item = _item(
        "attributed-background-study",
        """\
## Background

Smith et al. report that a primary focus of this study involves comparing
different labels, specifically nova and vetus. Their respondents describe
vetus as outdated and derogatory.
""",
    )

    _assert_no_positive_authority(item)


def test_explicit_related_work_section_cannot_be_promoted_by_local_wording() -> None:
    item = _item(
        "related-work-study",
        (
            "A primary focus of this study involves comparing different labels, "
            "specifically nova and vetus. Respondents describe vetus as outdated "
            "and derogatory."
        ),
        section_id="related_work",
    )

    _assert_no_positive_authority(item)


def test_future_study_cannot_be_promoted_by_local_wording() -> None:
    item = _item(
        "future-study",
        (
            "A primary focus of this study will involve comparing different "
            "labels, specifically nova and vetus. Future respondents may describe "
            "vetus as outdated and derogatory."
        ),
        section_id="future_work",
    )

    _assert_no_positive_authority(item)


def test_prospective_focus_without_future_heading_remains_unverified() -> None:
    item = _item(
        "prospective-study",
        (
            "A primary focus of this study will involve comparing different "
            "labels, specifically nova and vetus. Respondents may describe vetus "
            "as outdated and derogatory."
        ),
    )

    _assert_no_positive_authority(item)


def test_modal_outside_target_proposition_does_not_block_local_ownership() -> None:
    item = _item(
        "modal-outside-target",
        (
            "These labels may convey different social meanings. A primary focus "
            "of this study involves comparing different labels, specifically nova "
            "and vetus. Respondents describe vetus as outdated and derogatory."
        ),
    )

    resolution = resolve_closed_scope_boolean(QUESTION, [item])
    assert resolution is not None
    assert resolution.polarity == "yes"
    assert resolution.decision.actor == "current_paper"
    assert boolean_proposition_candidate_score(QUESTION, item) > 0.0


def test_current_focus_and_cited_different_label_are_not_stitched() -> None:
    item = _item(
        "different-label",
        (
            "A primary focus of this study involves comparing interface labels, "
            "specifically nova and vetus. Prior work describes the unrelated term "
            "antiqua as outdated and derogatory."
        ),
    )

    _assert_no_positive_authority(item)
