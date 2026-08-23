from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.execution_recovery_events import (
    recovery_has_progress,
    recovery_trace_fields,
)
from ktem.docqa.typed_retrieval_recovery import typed_retrieval_recovery_trace
from ktem.docqa.verification import VerifyDecision

QUESTION = "Do the authors conduct experiments on the dataset?"
IRRELEVANT = "The paper introduces a conversational system."
EXACT_AUTHORITY = "We conduct experiments on the dataset and report the results."


def _request(*, route_policy: str = "doc") -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=["doc_text", "hybrid"],
        selected_file_ids=["runtime-paper"],
        origin="benchmark",
    )


def _evidence(runtime_source_id: str, evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": runtime_source_id,
        "runtime_source_id": runtime_source_id,
        "evaluation_source_id": "qasper-paper-stable",
        "document_id": "qasper-paper-stable",
        "section_id": "experiments",
        "page_label": "4",
        "text": text,
    }


def _bundle(runtime_source_id: str, evidence_id: str) -> EvidenceBundle:
    item = _evidence(runtime_source_id, evidence_id, IRRELEVANT)
    return EvidenceBundle(
        route="doc_text",
        items=[item],
        metadata={
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "statement_kind": "boolean_proposition",
                        "required_for_verification": True,
                        "status": "retrieved_unverified",
                        "evidence_ids": [identity_of(item).key],
                    }
                ]
            }
        },
    )


def test_typed_retrieval_no_progress_ignores_runtime_uuid_churn() -> None:
    initial = _bundle(
        "11111111-1111-4111-8111-111111111111",
        "runtime-evidence-a",
    )
    recovered = _bundle(
        "22222222-2222-4222-8222-222222222222",
        "runtime-evidence-b",
    )

    trace = typed_retrieval_recovery_trace(
        _request(),
        initial,
        recovered,
        [{"query": QUESTION}],
        SimpleNamespace(status="poor"),
    )

    assert trace["evidence_ids_before"] != trace["evidence_ids_after"]
    assert trace["semantic_evidence_ids_before"] == (
        trace["semantic_evidence_ids_after"]
    )
    assert trace["new_semantic_evidence_ids"] == []
    assert trace["semantic_slot_state_changed"] is False
    assert trace["recovery_outcome"] == "no_progress"
    assert trace["stop_reason"] == "recovery_no_progress"


def test_verifier_recovery_progress_ignores_runtime_uuid_churn() -> None:
    fields = recovery_trace_fields(
        _request(),
        VerifyDecision(
            mode="strict",
            status="unknown",
            reason="authority missing",
            typed_authority={"reason": "exact_boolean_authority_missing"},
        ),
        _bundle(
            "11111111-1111-4111-8111-111111111111",
            "runtime-evidence-a",
        ),
        _bundle(
            "22222222-2222-4222-8222-222222222222",
            "runtime-evidence-b",
        ),
    )

    assert fields["new_evidence_ids"]
    assert fields["new_semantic_evidence_ids"] == []
    assert fields["semantic_slot_state_changed"] is False
    assert fields["proposition_binding_changed"] is False
    assert recovery_has_progress(fields) is False


def test_first_semantic_pack_is_a_real_recovery_change() -> None:
    fields = recovery_trace_fields(
        _request(),
        VerifyDecision(
            mode="strict",
            status="unknown",
            reason="authority missing",
            typed_authority={"reason": "exact_boolean_authority_missing"},
        ),
        None,
        _bundle("stable-source", "stable-evidence"),
    )

    assert fields["semantic_pack_digest_before"] == ""
    assert fields["semantic_pack_digest_after"]
    assert fields["semantic_pack_digest_applicable"] is True
    assert fields["semantic_pack_digest_changed"] is True
    assert recovery_has_progress(fields) is True


@pytest.mark.parametrize(
    ("recovery_kind", "change_semantic_pack"),
    (
        ("proposition_repair", False),
        ("proof_repair", False),
        ("quote_rebind", False),
        ("evidence_retrieval", True),
    ),
)
def test_recovery_kind_reverifies_only_after_semantic_pack_digest_changes(
    recovery_kind: str,
    change_semantic_pack: bool,
) -> None:
    initial = _bundle("stable-source", "stable-evidence")
    recovered = _bundle("stable-source", "stable-evidence")
    initial.metadata["semantic_proposition_verifier"] = {
        "reason": recovery_kind,
        "recovery_transitions": (
            [{"to": recovery_kind}]
            if recovery_kind in {"proof_repair", "proposition_repair"}
            else []
        ),
    }
    if change_semantic_pack:
        recovered.items[0]["text"] = EXACT_AUTHORITY

    fields = recovery_trace_fields(
        _request(),
        VerifyDecision(
            mode="strict",
            status="unknown",
            reason="authority missing",
            typed_authority={"reason": "exact_boolean_authority_missing"},
        ),
        initial,
        recovered,
    )

    assert fields["recovery_transition"]["to"] == recovery_kind
    assert fields["semantic_pack_digest_changed"] is change_semantic_pack
    assert fields["recovery_transition"]["status"] == (
        "pack_changed" if change_semantic_pack else "no_pack_change"
    )
    assert recovery_has_progress(fields) is change_semantic_pack


@pytest.mark.parametrize(
    ("current_reason", "change_semantic_pack", "expected_kind"),
    (
        ("joint_entailment_rejected", False, "proof_repair"),
        ("typed_conclusion_quantifier_rejected", False, "proof_repair"),
        ("semantic_premise_quote_unbound", False, "quote_rebind"),
        ("joint_entailment_rejected", True, "evidence_retrieval"),
    ),
)
def test_current_rejection_outranks_historical_proposition_repair(
    current_reason: str,
    change_semantic_pack: bool,
    expected_kind: str,
) -> None:
    initial = _bundle("stable-source", "stable-evidence")
    recovered = _bundle("stable-source", "stable-evidence")
    initial.metadata["semantic_proposition_verifier"] = {
        "reason": "semantic_entailment_audit_rejected",
        "audit_reason": current_reason,
        "recovery_transitions": [
            {
                "from": "question_proposition",
                "to": "proposition_repair",
                "reason": "question_proposition_predicate_unspecified",
            }
        ],
        "rejected_transactions": [{"runtime_rejection_reason": current_reason}],
    }
    if change_semantic_pack:
        recovered.items[0]["text"] = EXACT_AUTHORITY

    fields = recovery_trace_fields(
        _request(),
        VerifyDecision(
            mode="strict",
            status="unknown",
            reason="authority missing",
            typed_authority={"reason": "exact_boolean_authority_missing"},
        ),
        initial,
        recovered,
    )

    assert fields["recovery_transition"]["to"] == expected_kind
    assert fields["proposition_binding_changed"] is change_semantic_pack


def test_retrieval_no_progress_stops_before_route_switch() -> None:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        if decision.legacy_route == "hybrid":
            return {
                "evidence": [
                    _evidence(
                        "33333333-3333-4333-8333-333333333333",
                        "hybrid-authority",
                        EXACT_AUTHORITY,
                    )
                ]
            }
        runtime_id = (
            "11111111-1111-4111-8111-111111111111"
            if request.retrieval_round_id == 1
            else "22222222-2222-4222-8222-222222222222"
        )
        return {
            "evidence": [
                _evidence(
                    runtime_id,
                    f"runtime-evidence-{request.retrieval_round_id}",
                    IRRELEVANT,
                )
            ]
        }

    result = execute_controller_turn(
        _request(route_policy="auto"),
        retrieve=retrieve,
        generate=lambda *_args: "yes",
    )

    assert calls == [("doc_text", 1), ("doc_text", 2)]
    assert result.answer == ABSTAIN_MESSAGE
    assert not any(
        event.get("stage") in {"route_switch", "route_switch_attempt"}
        for event in result.controller_trace
    )
    [recovery] = [
        event
        for event in result.controller_trace
        if event.get("stage") == "targeted_retrieval"
    ]
    assert recovery["recovery_outcome"] == "no_progress"
    assert recovery["stop_reason"] == "recovery_no_progress"
    assert recovery["new_semantic_evidence_ids"] == []
