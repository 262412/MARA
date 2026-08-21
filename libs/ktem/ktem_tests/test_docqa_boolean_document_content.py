from __future__ import annotations

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_proposition_context import contextual_actor
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision


def test_paper_topic_question_commits_grounded_body_content_authority() -> None:
    question = "Does the paper explore extraction from electronic health records?"
    evidence = _biomedical_scope_evidence(section_title="Introduction")
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    request = DocQARequest(
        prompt=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=plan,
        query_plan_state_version=1,
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=[evidence]),
        "yes",
    )

    assert decision.status == "supported"
    assert decision.typed_authority["state"] == "verified_support"
    [atom] = decision.typed_authority["authority_atoms"]
    assert atom["actor"] == "current_paper"


def test_author_action_question_does_not_inherit_paper_content_scope() -> None:
    evidence = _biomedical_scope_evidence(section_title="Introduction")

    authority = boolean_claim_authority(
        "Do the authors extract information from electronic health records?",
        "yes",
        [evidence],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_related_work_does_not_inherit_paper_content_scope() -> None:
    evidence = _biomedical_scope_evidence(section_title="Related Work")

    authority = boolean_claim_authority(
        "Does the paper explore extraction from electronic health records?",
        "yes",
        [evidence],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()


def test_nested_content_verb_does_not_change_an_unknown_actor() -> None:
    actor = contextual_actor(
        "Extraction from electronic health records is explored.",
        "",
        "body",
        question=(
            "Does the paper cite prior work that explores extraction from "
            "electronic health records?"
        ),
    )

    assert actor == "unknown"


def _biomedical_scope_evidence(*, section_title: str) -> dict[str, str]:
    return {
        "source_id": "biomedical-primer",
        "evidence_id": "biomedical-scope",
        "section_title": section_title,
        "text": (
            "This paper provides an overview of Biomedical Information "
            "Extraction.\n\n## Introduction\n\nBioIE systems aim to extract "
            "information from a wide spectrum of "
            "articles including medical literature, biological literature, "
            "electronic health records, etc."
        ),
    }
