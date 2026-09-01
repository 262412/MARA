from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.typed_proposition_authority import resolve_qasper_authority_transaction
from ktem.docqa.verification_logic import (
    _boolean_verification,
    _decision_for_claim_results,
)

QUESTION = "Does the report evaluate the model?"


def _item(evidence_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def _request(
    slots: tuple[EvidenceSlot, ...],
    *,
    requires_distinct_evidence: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        query_plan=QueryPlan(
            answer_type="boolean",
            question_type="cross_page",
            plan_id="synthetic-qasper-plan",
            subqueries=(QUESTION,),
            evidence_slots=slots,
            constraints={
                "verification_domain": "qasper",
                "requires_distinct_evidence": requires_distinct_evidence,
            },
        ),
        query_plan_state_version=0,
        verification_domain="qasper",
        task_type="boolean",
    )


def _decision(items: list[dict[str, str]]):
    verification = _boolean_verification(QUESTION, "yes", items)
    assert verification is not None
    claims, results = verification
    return _decision_for_claim_results(
        "strict",
        "good",
        claims,
        results,
        items,
        prompt=QUESTION,
        domain="qasper",
    )


def test_boolean_transaction_does_not_reuse_one_atom_for_each_required_slot() -> None:
    item = _item("only-support", "The report evaluates the model on task one.")
    evidence_id = identity_of(item).key
    slots = tuple(
        EvidenceSlot(
            slot_id=slot_id,
            role="support",
            statement_kind=(
                "boolean_proposition" if slot_id.endswith("proposition") else ""
            ),
            required_for_retrieval=False,
            required_for_verification=True,
            evidence_ids=(evidence_id,),
        )
        for slot_id in (
            "support:proposition",
            "support:left_subject",
            "support:right_subject",
        )
    )

    result = resolve_qasper_authority_transaction(
        _request(slots, requires_distinct_evidence=True),
        _decision([item]),
        EvidenceBundle(route="doc_text", items=[item]),
        question=QUESTION,
        answer="yes",
        domain="qasper",
    )

    assert result is not None
    assert result.typed_authority["state"] == "missing"
    assert result.typed_authority["reason"] == (
        "required_support_slot_binding_incomplete"
    )
    assert result.verified_citations == []


def test_boolean_transaction_binds_each_required_slot_to_its_exact_atom() -> None:
    items = [
        _item("left-support", "The report evaluates the model on task one."),
        _item("right-support", "The report evaluates the model on task two."),
    ]
    left_id, right_id = (identity_of(item).key for item in items)
    slots = (
        EvidenceSlot(
            slot_id="support:proposition",
            role="support",
            statement_kind="boolean_proposition",
            required_for_retrieval=False,
            required_for_verification=True,
            evidence_ids=(left_id, right_id),
        ),
        EvidenceSlot(
            slot_id="support:left_subject",
            role="support",
            required_for_verification=True,
            evidence_ids=(left_id,),
        ),
        EvidenceSlot(
            slot_id="support:right_subject",
            role="support",
            required_for_verification=True,
            evidence_ids=(right_id,),
        ),
    )

    request = _request(slots, requires_distinct_evidence=True)
    result = resolve_qasper_authority_transaction(
        request,
        _decision(items),
        EvidenceBundle(route="doc_text", items=items),
        question=QUESTION,
        answer="yes",
        domain="qasper",
    )

    assert result is not None
    assert result.typed_authority["state"] == "verified_support"
    assert result.typed_authority["slot_bindings"] == {
        "support:proposition": [left_id, right_id],
        "support:left_subject": [left_id],
        "support:right_subject": [right_id],
    }
    assert [
        atom["evidence_id"] for atom in result.typed_authority["authority_atoms"]
    ] == [
        left_id,
        right_id,
    ]
