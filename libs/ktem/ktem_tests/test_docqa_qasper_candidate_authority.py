from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_verification import verify_generated_answer
from ktem.docqa.pipeline_stage_timings import PipelineStageTimings
from ktem.docqa.query_plan_schema import EvidenceSlot
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.typed_proposition_authority_slots import boolean_slot_bindings
from ktem.docqa.verification import verify_decision
from ktem_tests.semantic_entailment_test_helpers import audited_verdict

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        controller_question=QUESTION,
        retrieval_query=QUESTION,
        dataset_family="qasper",
        task_type="qasper_qa",
        answer_type="boolean",
        origin="cli",
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
    )


def _items() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "cross-lingual",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "We evaluated transfer in the cross-lingual setting.",
        },
        {
            "evidence_id": "single-language",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "The same experiment included single-language baselines for comparison.",
        },
    ]


def _yes_response(
    request: Any,
    question: str,
    candidate: str,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    slot_ids = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    value = audited_verdict(
        {
            "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
            "verdict": "yes",
            "support_mode": "evidence_set",
            "proof_mode": "composite_conjunction",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "evidence_id": identity_of(item).key,
                    "quote": item["text"],
                    "proposition_fragment": fragment,
                    "supports_slot_ids": [
                        slot_id
                        for slot_id in slot_ids
                        if slot_id == "support:proposition" or slot_id.endswith(side)
                    ],
                }
                for item, fragment, side in zip(
                    bundle.items,
                    (
                        "cross-lingual evaluation was performed",
                        "single-language baselines were included for comparison",
                    ),
                    ("left_subject", "right_subject"),
                )
            ],
            "verifier": {
                "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                "model": "candidate-verifier-test",
                "seed": 7,
            },
        },
        question,
    )
    value.update(
        candidate_verification_contract="candidate_proposition_verification.v2",
        verifier_input_candidate=candidate,
        candidate_verification_status=(
            "supported" if candidate == "yes" else "contradicted"
        ),
        replacement_candidate_allowed=False,
    )
    bundle.metadata["semantic_proposition_verifier"] = {
        "candidate_label": candidate,
        "candidate_verification_status": value["candidate_verification_status"],
    }
    return value


def test_qasper_verifier_cannot_replace_a_contradicted_candidate() -> None:
    bundle = EvidenceBundle(route="doc_text", items=_items())
    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "no",
        proposition_verifier=_yes_response,
    )

    assert decision.status == "unsupported"
    assert decision.action == "abstain"
    assert decision.candidate_label == "no"
    assert decision.verifier_input_candidate == "no"
    assert decision.verifier_candidate_status == "contradicted"
    assert decision.canonical_answer_polarity == ""
    assert decision.semantic_correction_applied is False
    assert decision.replacement_candidate_allowed is False


def test_qasper_verifier_commits_only_the_supported_input_candidate() -> None:
    bundle = EvidenceBundle(route="doc_text", items=_items())
    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
        proposition_verifier=_yes_response,
    )

    assert decision.status == "supported"
    assert decision.candidate_label == "yes"
    assert decision.verifier_candidate_status == "supported"
    assert decision.canonical_answer_polarity == "yes"
    assert decision.semantic_correction_applied is False
    assert decision.typed_authority["state"] == "verified_support"


def test_qasper_supported_unanswerable_is_a_verified_abstention() -> None:
    def verifier(
        _request: Any,
        _question: str,
        candidate: str,
        bundle: EvidenceBundle,
    ) -> dict[str, Any]:
        bundle.metadata["semantic_proposition_verifier"] = {
            "candidate_label": candidate,
            "candidate_verification_status": "supported",
        }
        return {
            "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
            "verdict": "insufficient_evidence",
            "support_mode": "evidence_set",
            "proof_mode": "none",
            "jointly_complete": False,
            "each_premise_required": False,
            "premises": [],
            "verifier": {
                "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                "model": "candidate-verifier-test",
                "seed": 7,
            },
            "candidate_verification_contract": (
                "candidate_proposition_verification.v2"
            ),
            "verifier_input_candidate": candidate,
            "candidate_verification_status": "supported",
            "replacement_candidate_allowed": False,
        }

    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_items()),
        "unanswerable",
        proposition_verifier=verifier,
    )

    assert decision.status == "supported"
    assert decision.candidate_label == "unanswerable"
    assert decision.verifier_candidate_status == "supported"
    assert decision.typed_authority["state"] == "verified_abstention"
    assert decision.canonical_answer_polarity == ""


def test_empty_candidate_fails_closed_without_asking_verifier_to_answer() -> None:
    calls = 0

    def forbidden_verify(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("verifier must not answer an empty candidate")

    class Guardrail:
        def __init__(self, status: str, action: str, reason: str) -> None:
            self.status = status
            self.action = action
            self.reason = reason

    request = _request()
    request.origin = "benchmark"
    bundle = EvidenceBundle(route="doc_text", items=_items())
    answer, decision, guardrail, trace = verify_generated_answer(
        request,
        object(),
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "",
        None,
        [],
        PipelineStageTimings(),
        verify=forbidden_verify,
        guardrail_factory=Guardrail,
        abstain_message="ABSTAIN",
        ragtruth_empty_answer="{}",
    )

    assert calls == 0
    assert answer == "ABSTAIN"
    assert decision.status == "not_enough_evidence"
    assert guardrail.action == "abstain"
    assert trace[-1]["action"] == "fail_closed_abstention"
    assert bundle.metadata["typed_boolean_generation_recovery"] == (
        "empty_generation_rejected_without_verifier_call"
    )


def test_single_proposition_slot_never_binds_an_unlisted_atom() -> None:
    slot = EvidenceSlot(
        slot_id="support:boolean_proposition",
        role="support",
        statement_kind="boolean_proposition",
        evidence_ids=("span:paper:authority",),
    )
    request = SimpleNamespace(query_plan=SimpleNamespace(constraints={}))
    atoms = [
        {
            "evidence_id": "span:paper:distractor",
            "evidence_ref": "span:paper:distractor#quote:0:10",
        },
        {
            "evidence_id": "span:paper:authority",
            "evidence_ref": "span:paper:authority#quote:0:10",
        },
    ]

    bindings, slot_refs, selected = boolean_slot_bindings(
        request,
        [slot],
        atoms,
    )

    assert bindings == {"support:boolean_proposition": ("span:paper:authority",)}
    assert slot_refs == {}
    assert [atom["evidence_id"] for atom in selected or []] == ["span:paper:authority"]
