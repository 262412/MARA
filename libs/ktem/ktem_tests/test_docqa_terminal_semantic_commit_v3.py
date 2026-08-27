from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.engine_terminal_projection import engine_terminal_projection
from ktem.docqa.execution_contracts import ABSTAIN_MESSAGE
from ktem.docqa.execution_models import GuardrailDecision
from ktem.docqa.terminal_semantic_commit import (
    build_terminal_semantic_commit,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)
from ktem.docqa.verification import VerifyDecision


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _verified_projection() -> tuple[VerifyDecision, GuardrailDecision, EvidenceBundle]:
    verify = VerifyDecision(
        mode="strict",
        status="supported",
        reason="The claim is directly supported.",
        action="generate",
        verified_citations=["evidence-1"],
    )
    guardrail = GuardrailDecision("ok", "return", "verified")
    bundle = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "evidence-1", "text": "Direct support."}],
        metadata={
            "verified_claim_support_evidence": [
                {"evidence_id": "evidence-1", "quote": "Direct support."}
            ]
        },
    )
    return verify, guardrail, bundle


def _legacy_v2_commit(*, answer_status: str = "answered") -> dict:
    unsigned = {
        "contract_id": "terminal_semantic_commit.v2",
        "semantic_answer": (
            "The method uses direct evidence."
            if answer_status == "answered"
            else "unanswerable"
        ),
        "answer_status": answer_status,
        "verify_decision": {"status": "supported"},
        "guardrail_decision": {"action": "return"},
        "authoritative_evidence": [{"evidence_id": "evidence-1"}],
        "citations": ["evidence-1"],
        "state_version": 2,
    }
    return {**unsigned, "projection_hash": _hash(unsigned)}


def test_v3_answered_commit_separates_semantic_and_presentation_answers() -> None:
    verify, guardrail, bundle = _verified_projection()

    commit = build_terminal_semantic_commit(
        "The method uses direct evidence.",
        verify,
        guardrail,
        bundle,
        presentation_answer="The method uses direct evidence. [1]",
    ).as_dict()

    assert commit == {
        "contract_id": "terminal_semantic_commit.v3",
        "semantic_answer": "The method uses direct evidence.",
        "presentation_answer": "The method uses direct evidence. [1]",
        "outcome": "answered",
        "outcome_reason": "",
        "answer_status": "answered",
        "verify_decision": verify.as_dict(),
        "guardrail_decision": guardrail.as_dict(),
        "authoritative_evidence": [
            {"evidence_id": "evidence-1", "quote": "Direct support."}
        ],
        "citations": ["evidence-1"],
        "projection_hash": commit["projection_hash"],
        "state_version": 3,
    }
    assert terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == "answered"


def test_v3_safe_abstention_preserves_presentation_and_reason() -> None:
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {"status": "unknown", "action": "abstain", "reason": "No exact support."},
        {"status": "unknown", "action": "abstain", "reason": "Fail closed."},
        {"metadata": {}},
    ).as_dict()

    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert commit["outcome"] == "safe_abstention"
    assert commit["outcome_reason"] == "Fail closed."
    assert commit["answer_status"] == "abstained"
    assert terminal_commit_projection_present(commit)


@pytest.mark.parametrize(
    "outcome",
    [
        "answered",
        "safe_abstention",
        "execution_failed",
        "timeout",
        "cancelled",
    ],
)
def test_v3_outcome_taxonomy_is_closed_and_mutually_exclusive(outcome: str) -> None:
    verify, guardrail, bundle = _verified_projection()
    answer = "The method uses direct evidence."
    if outcome != "answered":
        answer = ABSTAIN_MESSAGE

    commit = build_terminal_semantic_commit(
        answer,
        verify,
        guardrail,
        bundle,
        outcome=outcome,
        outcome_reason="" if outcome == "answered" else f"{outcome} reason",
    ).as_dict()

    assert commit["outcome"] == outcome
    assert commit["answer_status"] == (
        "answered" if outcome == "answered" else "abstained"
    )
    assert terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == outcome


@pytest.mark.parametrize(
    ("answer_status", "expected_outcome"),
    [("answered", "answered"), ("abstained", "safe_abstention")],
)
def test_v2_commit_remains_readable(
    answer_status: str,
    expected_outcome: str,
) -> None:
    commit = _legacy_v2_commit(answer_status=answer_status)

    assert terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == expected_outcome


def test_commit_hash_rejects_tampering_and_hash_mismatch() -> None:
    verify, guardrail, bundle = _verified_projection()
    commit = build_terminal_semantic_commit(
        "The method uses direct evidence.", verify, guardrail, bundle
    ).as_dict()

    tampered = deepcopy(commit)
    tampered["semantic_answer"] = "tampered"
    assert not terminal_commit_projection_present(tampered)

    mismatched = deepcopy(commit)
    mismatched["projection_hash"] = "0" * 64
    assert not terminal_commit_projection_present(mismatched)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outcome", "unknown_failure"),
        ("answer_status", "answered"),
        ("state_version", 2),
        ("verify_decision", []),
    ],
)
def test_rehashed_invalid_v3_commit_is_rejected(field: str, value: object) -> None:
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {"status": "unknown", "action": "abstain"},
        {"status": "unknown", "action": "abstain"},
        {"metadata": {}},
    ).as_dict()
    commit[field] = value
    unsigned = {key: item for key, item in commit.items() if key != "projection_hash"}
    commit["projection_hash"] = _hash(unsigned)

    assert not terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == ""


def test_builder_rejects_an_invalid_requested_outcome() -> None:
    verify, guardrail, bundle = _verified_projection()

    with pytest.raises(ValueError, match="Unsupported terminal outcome"):
        build_terminal_semantic_commit(
            "The method uses direct evidence.",
            verify,
            guardrail,
            bundle,
            outcome="unknown_failure",
        )


@pytest.mark.parametrize(
    "outcome",
    ["safe_abstention", "execution_failed", "timeout", "cancelled"],
)
def test_builder_rejects_non_answered_outcome_with_answered_semantics(
    outcome: str,
) -> None:
    verify, guardrail, bundle = _verified_projection()

    with pytest.raises(ValueError, match="does not match semantic answer"):
        build_terminal_semantic_commit(
            "The method uses direct evidence.",
            verify,
            guardrail,
            bundle,
            outcome=outcome,
        )


def test_v3_commit_copies_nested_projection_inputs() -> None:
    verify = {"status": "supported", "verified_citations": ["evidence-1"]}
    guardrail = {"status": "ok", "action": "return"}
    bundle = {
        "metadata": {
            "verified_claim_support_evidence": [
                {"evidence_id": "evidence-1", "quote": "Direct support."}
            ]
        }
    }
    commit = build_terminal_semantic_commit(
        "The method uses direct evidence.", verify, guardrail, bundle
    )
    expected = commit.as_dict()

    verify["status"] = "unknown"
    guardrail["action"] = "abstain"
    bundle["metadata"]["verified_claim_support_evidence"][0]["quote"] = "changed"
    first_read = commit.as_dict()
    first_read["verify_decision"]["status"] = "changed"

    assert commit.as_dict() == expected


def test_engine_projection_exposes_v3_without_changing_normal_semantics() -> None:
    verify, guardrail, bundle = _verified_projection()

    answer, state, projected_verify, projected_guardrail, projected_bundle, _ = (
        engine_terminal_projection(
            "The method uses direct evidence. [1]",
            verify,
            guardrail,
            bundle,
        )
    )

    assert answer == "The method uses direct evidence. [1]"
    assert state["answer"] == answer
    assert state["presentation_answer"] == "The method uses direct evidence. [1]"
    assert state["terminal_outcome"] == "answered"
    assert state["terminal_semantic_commit"]["semantic_answer"] == answer
    assert state["terminal_semantic_commit"]["contract_id"] == (
        "terminal_semantic_commit.v3"
    )
    assert projected_verify == verify.as_dict()
    assert projected_guardrail == guardrail.as_dict()
    assert projected_bundle == bundle.as_dict()
