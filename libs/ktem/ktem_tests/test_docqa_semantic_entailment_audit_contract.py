from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_authority_derivation import (
    boolean_derivation_contract_status,
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision
from ktem_tests.semantic_entailment_test_helpers import audited_verdict

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _items() -> list[dict[str, str]]:
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
            "text": (
                "The same experiment included single-language baselines for comparison."
            ),
        },
    ]


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="general",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="general",
        ),
    )


def _verdict(*, audited: bool) -> dict[str, Any]:
    request = _request()
    slot_ids = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    premises = [
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
            _items(),
            (
                "cross-lingual evaluation was performed",
                "single-language baselines were included for comparison",
            ),
            ("left_subject", "right_subject"),
        )
    ]
    response: dict[str, Any] = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "yes",
        "support_mode": "evidence_set",
        "proof_mode": "composite_conjunction",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": premises,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": "proposal-test-double",
            "seed": 7,
        },
    }
    response = audited_verdict(response, QUESTION)
    if not audited:
        response.pop("entailment_audit")
    return response


def _verify(response: dict[str, Any]) -> tuple[Any, EvidenceBundle]:
    bundle = EvidenceBundle(route="doc_text", items=_items())
    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "unanswerable",
        proposition_verifier=lambda *_args: response,
    )
    return decision, bundle


def test_self_attested_semantic_proposal_without_audit_cannot_publish() -> None:
    decision, bundle = _verify(_verdict(audited=False))

    assert decision.status != "supported"
    assert decision.typed_authority["state"] == "missing"
    assert bundle.metadata["semantic_proposition_authority"]["reason"] == (
        "semantic_entailment_audit_missing"
    )


def test_reidentified_derivation_cannot_hide_a_tampered_audit_binding() -> None:
    decision, _bundle = _verify(_verdict(audited=True))
    [derivation] = deepcopy(decision.typed_authority["authority_derivations"])
    derivation["verifier_attestation"]["entailment_audit"]["proposal_digest"] = "0" * 64
    derivation["derivation_id"] = boolean_derivation_id(
        boolean_derivation_identity_payload(
            rule_id=derivation["rule_id"],
            premise_refs=derivation["premise_refs"],
            conclusion=derivation["conclusion"],
            required_argument_tokens=derivation["required_argument_tokens"],
            bindings=derivation["bindings"],
            support_mode=derivation["support_mode"],
            verifier_attestation=derivation["verifier_attestation"],
            premise_contributions=derivation["premise_contributions"],
        )
    )

    assert (
        boolean_derivation_contract_status(
            derivation,
            decision.typed_authority["authority_atoms"],
            question=QUESTION,
            canonical_polarity="yes",
        )
        == "semantic_entailment_audit_binding_invalid"
    )
