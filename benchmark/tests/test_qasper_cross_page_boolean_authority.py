from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_evidence_scope import classify_boolean_evidence_set
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.qasper_evidence_priorities import qasper_evidence_priorities
from benchmark.qasper_proposition_conflict import resolve_boolean_conflict

QUESTION = "Across pages 1 and 2, did the authors release the code?"
POSITIVE_QUOTE = "The authors released the code publicly with the paper."
NEGATIVE_QUOTE = "The authors did not release the code for the final evaluated system."


class _Verifier:
    def __init__(self) -> None:
        self.responses = [
            (
                '{"verdict":"yes_complete","evidence_ref":"",'
                f'"evidence_quote":"{POSITIVE_QUOTE}"}}'
            ),
            (
                '{"verdict":"yes_complete","evidence_ref":"E1:S1",'
                f'"evidence_quote":"{POSITIVE_QUOTE}"}}'
            ),
        ]

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return type(
            "Result",
            (),
            {"text": self.responses.pop(0)},
        )()


def _page(evidence_id: str, page_label: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "document_id": "qasper_contract_cross_page",
        "page_label": page_label,
        "modality": "image",
        "evidence_level": "page",
        "text": text,
    }


def _artifact_pages() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        _page(
            "stable-page-1",
            "1",
            (
                "Contract Smoke Study - Methods\n"
                f"{POSITIVE_QUOTE}\n"
                "The release statement applies to the final evaluated system.\n"
                "Page 1"
            ),
        ),
        _page(
            "stable-page-2",
            "2",
            (
                "Contract Smoke Study - Correction\n"
                f"{NEGATIVE_QUOTE}\n"
                "This correction explicitly supersedes the earlier release "
                "statement.\nPage 2"
            ),
        ),
    )


def test_artifact_shaped_cross_page_authority_reaches_real_conflict() -> None:
    page_1, page_2 = _artifact_pages()
    evidence_items = [page_1, page_2]
    plan = bind_evidence_slots(
        build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        evidence_items,
    )
    prediction = {
        "evidence_metadata": {
            "query_plan": plan.as_dict(),
            "selected_evidence": evidence_items,
            "generation_context_evidence": evidence_items,
        }
    }
    priorities = qasper_evidence_priorities(
        prediction,
        evidence_items,
        question=QUESTION,
        candidate_answer="unanswerable",
    )
    classified = classify_boolean_evidence_set(
        QUESTION,
        "yes",
        evidence_items,
    )

    assert classified.supports[0].proposition.claim_key == (
        classified.contradicts[0].proposition.claim_key
    )
    assert priorities.required_slot_ids == (
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    )
    assert priorities.missing_required_slot_ids == ()
    assert priorities.required_evidence_ids == (
        identity_of(page_1).key,
        identity_of(page_2).key,
    )

    result = verify_qasper_answerability(
        _Verifier(),
        question=QUESTION,
        evidence="\n\n".join(item["text"] for item in evidence_items),
        evidence_items=evidence_items,
        required_evidence_ids=list(priorities.required_evidence_ids),
        required_slot_ids=list(priorities.required_slot_ids),
        missing_required_slot_ids=list(priorities.missing_required_slot_ids),
        missing_required_evidence_ids=list(priorities.missing_required_evidence_ids),
        priority_evidence_ids=list(priorities.generation_evidence_ids),
        candidate_answer="unanswerable",
        answer_type="boolean",
    )

    assert result.answer == "unanswerable"
    assert result.trace["verifier_required_slot_authority_count"] == "3"
    assert result.trace["verifier_required_evidence_coverage"] == "1.000000"
    assert result.trace["conflict_status"] == "balanced_conflict"
    assert result.trace["reason"] != "missing_required_evidence_authority"
    assert set(result.trace["verifier_required_evidence_ids"].split(",")) == {
        identity_of(page_1).key,
        identity_of(page_2).key,
    }


def test_same_polarity_pages_do_not_create_a_balanced_conflict() -> None:
    page_1 = _page("page-1", "1", f"{POSITIVE_QUOTE} Page 1")
    page_2 = _page(
        "page-2",
        "2",
        "The authors also released the code for the final system. Page 2",
    )

    action, answer, trace = resolve_boolean_conflict(
        "",
        QUESTION,
        candidate_polarity="yes",
        verdict="yes",
        evidence_items=[page_1, page_2],
    )

    assert action == "confirmed_candidate"
    assert answer == "yes"
    assert trace["conflict_status"] == "none"
