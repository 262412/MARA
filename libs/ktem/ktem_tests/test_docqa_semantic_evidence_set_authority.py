from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_authority_derivation import boolean_derivation_contract_status
from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_EVIDENCE_SET_RULE,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision
from ktem_tests.semantic_entailment_test_helpers import (
    audited_verdict as _audited_verdict,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _item(evidence_id: str, text: str, *, source_id: str = "paper") -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "section_id": "experiments",
        "text": text,
    }


def _premises() -> list[dict[str, Any]]:
    return [
        _item(
            "cross-lingual",
            "We compared cross-lingual evaluation.",
        ),
        _item(
            "single-language",
            "The same comparison included single-language evaluation.",
        ),
    ]


def _request(question: str = QUESTION) -> DocQARequest:
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="general",
    )
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="general",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=plan,
        query_plan_state_version=1,
    )


def _semantic_verdict(
    _request: Any,
    question: str,
    _answer: str,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    assert question == QUESTION
    return _audited_verdict(
        {
            "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
            "verdict": "yes",
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "evidence_id": identity_of(item).key,
                    "quote": item["text"],
                    "proposition_fragment": (
                        "We compared cross-lingual evaluation."
                        if index == 0
                        else "The same comparison included single-language evaluation."
                    ),
                    "supports_slot_ids": [
                        "support:proposition",
                        (
                            "support:left_subject"
                            if index == 0
                            else "support:right_subject"
                        ),
                    ],
                }
                for index, item in enumerate(bundle.items)
            ],
            "verifier": {
                "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                "model": "test-double",
                "seed": 7,
            },
        },
        question,
    )


def _same_item_semantic_verdict(
    _request: Any,
    question: str,
    _answer: str,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    evidence_id = identity_of(bundle.items[0]).key
    return _audited_verdict(
        {
            "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
            "verdict": "yes",
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "evidence_id": evidence_id,
                    "quote": "We compared cross-lingual evaluation.",
                    "proposition_fragment": "We compared cross-lingual evaluation.",
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:left_subject",
                    ],
                },
                {
                    "evidence_id": evidence_id,
                    "quote": (
                        "The same comparison included single-language evaluation."
                    ),
                    "proposition_fragment": (
                        "The same comparison included single-language evaluation."
                    ),
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:right_subject",
                    ],
                },
            ],
            "verifier": {
                "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                "model": "test-double",
                "seed": 7,
            },
        },
        question,
    )


def test_semantic_evidence_set_commits_one_typed_boolean_proposition() -> None:
    request = _request()
    items = _premises()
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "unanswerable",
        proposition_verifier=_semantic_verdict,
    )

    evidence_ids = {identity_of(item).key for item in items}
    assert decision.status == "supported"
    assert decision.canonical_answer_polarity == "yes"
    assert decision.boolean_authority_status == "verified_support"
    assert set(decision.verified_citations) == evidence_ids
    assert decision.authoritative_evidence_id == ""
    [claim] = decision.claim_results
    assert claim["authority_status"] == "semantic_evidence_set"
    [derivation] = decision.typed_authority["authority_derivations"]
    assert derivation["rule_id"] == SEMANTIC_EVIDENCE_SET_RULE
    assert derivation["support_mode"] == "evidence_set"
    assert derivation["verifier_attestation"]["model"] == "test-double"
    assert derivation["verifier_attestation"]["jointly_complete"] is True
    assert derivation["verifier_attestation"]["each_premise_required"] is True
    assert set(derivation["premise_evidence_ids"]) == evidence_ids
    assert {
        value["proposition_fragment"] for value in derivation["premise_contributions"]
    } == {
        "We compared cross-lingual evaluation.",
        "The same comparison included single-language evaluation.",
    }
    required_slots = [
        slot
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    assert required_slots
    assert all(slot.status == "verified_support" for slot in required_slots)
    assert {
        evidence_id for slot in required_slots for evidence_id in slot.evidence_ids
    } == (evidence_ids)


def test_semantic_evidence_set_binds_a_named_subject_across_local_spans() -> None:
    question = "Does Atlas contain data definitions for its 50 tasks?"
    items = [
        _item(
            "atlas-tasks",
            "Atlas contains definitions for its 50 tasks.",
        ),
        _item(
            "atlas-data",
            "Atlas contains data definitions for these tasks.",
        ),
    ]
    for item in items:
        item["section_id"] = "introduction"
    request = _request(question)
    [slot_id] = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]

    def verifier(*_args: Any) -> dict[str, Any]:
        return _audited_verdict(
            {
                "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                "verdict": "yes",
                "support_mode": "evidence_set",
                "jointly_complete": True,
                "each_premise_required": True,
                "premises": [
                    {
                        "evidence_id": identity_of(item).key,
                        "quote": item["text"],
                        "proposition_fragment": fragment,
                        "supports_slot_ids": [slot_id],
                    }
                    for item, fragment in zip(
                        items,
                        (
                            "Atlas contains definitions for its 50 tasks",
                            "Atlas contains data definitions for these tasks",
                        ),
                    )
                ],
                "verifier": {
                    "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                    "model": "test-double",
                    "seed": 7,
                },
            },
            question,
        )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "unanswerable",
        proposition_verifier=verifier,
    )

    assert decision.status == "supported"
    [derivation] = decision.typed_authority["authority_derivations"]
    assert derivation["verifier_attestation"]["scope_basis"] == (
        "named_question_subject"
    )


def test_semantic_local_spans_do_not_invent_a_current_author_action() -> None:
    question = "Did the authors use RegistryX for manual annotations?"
    items = [
        _item("registry", "RegistryX is a platform for annotation projects."),
        _item("labels", "Manual annotation labels can be stored in RegistryX."),
    ]
    for item in items:
        item["section_id"] = "introduction"
    request = _request(question)
    [slot_id] = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]

    def verifier(*_args: Any) -> dict[str, Any]:
        return _audited_verdict(
            {
                "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                "verdict": "yes",
                "support_mode": "evidence_set",
                "jointly_complete": True,
                "each_premise_required": True,
                "premises": [
                    {
                        "evidence_id": identity_of(item).key,
                        "quote": item["text"],
                        "proposition_fragment": f"registry premise {index}",
                        "supports_slot_ids": [slot_id],
                    }
                    for index, item in enumerate(items, start=1)
                ],
                "verifier": {
                    "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                    "model": "test-double",
                    "seed": 7,
                },
            },
            question,
        )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "yes",
        proposition_verifier=verifier,
    )

    assert decision.status != "supported"
    assert decision.typed_authority["state"] == "missing"


def test_semantic_no_requires_an_explicit_negative_relation() -> None:
    question = "Does Atlas contain private datasets for its 50 tasks?"
    items = [
        _item("atlas-public", "Atlas contains public datasets."),
        _item("atlas-tasks", "Atlas focuses on 50 tasks."),
    ]
    request = _request(question)
    [slot_id] = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]

    def verifier(*_args: Any) -> dict[str, Any]:
        return _audited_verdict(
            {
                "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                "verdict": "no",
                "support_mode": "evidence_set",
                "jointly_complete": True,
                "each_premise_required": True,
                "premises": [
                    {
                        "evidence_id": identity_of(item).key,
                        "quote": item["text"],
                        "proposition_fragment": f"positive premise {index}",
                        "supports_slot_ids": [slot_id],
                    }
                    for index, item in enumerate(items, start=1)
                ],
                "verifier": {
                    "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                    "model": "test-double",
                    "seed": 7,
                },
            },
            question,
        )

    bundle = EvidenceBundle(route="doc_text", items=items)
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "no",
        proposition_verifier=verifier,
    )

    assert decision.status != "supported"
    authority = bundle.metadata["semantic_proposition_authority"]
    assert authority["reason"] == "local_semantic_explicit_contradiction_missing"
    assert authority["polarity_contradiction_check"]["status"] == (
        "contradiction_detected"
    )
    assert authority["audit_verified_but_runtime_rejected"] is True


def test_semantic_no_can_bind_an_explicit_negative_relation() -> None:
    items = [
        _item("cross-lingual", "We evaluated cross-lingual transfer."),
        _item(
            "single-language",
            "We did not compare single-language evaluation.",
        ),
    ]
    request = _request()
    slot_ids = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]

    def verifier(*_args: Any) -> dict[str, Any]:
        return _audited_verdict(
            {
                "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                "verdict": "no",
                "support_mode": "evidence_set",
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
                            if slot_id == "support:proposition"
                            or slot_id.endswith(side)
                        ],
                    }
                    for item, fragment, side in zip(
                        items,
                        (
                            "cross-lingual evaluation was performed",
                            "single-language evaluation was not compared",
                        ),
                        ("left_subject", "right_subject"),
                    )
                ],
                "verifier": {
                    "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
                    "model": "test-double",
                    "seed": 7,
                },
            },
            QUESTION,
        )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "unanswerable",
        proposition_verifier=verifier,
    )

    assert decision.status == "supported"
    assert decision.canonical_answer_polarity == "no"


def test_semantic_verifier_cannot_join_premises_across_sources() -> None:
    items = _premises()
    items[1] = _item(
        "single-language",
        items[1]["text"],
        source_id="other-paper",
    )
    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=items),
        "yes",
        proposition_verifier=_semantic_verdict,
    )

    assert decision.status != "supported"
    assert decision.verified_citations == []
    assert decision.typed_authority["state"] == "missing"


def test_semantic_verifier_rejects_a_partially_malformed_premise_set() -> None:
    def malformed_premise(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verdict = _semantic_verdict(*args, **kwargs)
        verdict["premises"].insert(1, "not-a-premise")
        return verdict

    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_premises()),
        "yes",
        proposition_verifier=malformed_premise,
    )

    assert decision.status != "supported"
    assert decision.verified_citations == []
    assert decision.typed_authority["state"] == "missing"


def test_semantic_verifier_can_bind_two_nonoverlapping_spans_in_one_item() -> None:
    item = _item(
        "joint-chunk",
        (
            "We compared cross-lingual evaluation. "
            "The same comparison included single-language evaluation."
        ),
    )

    bundle = EvidenceBundle(route="doc_text", items=[item])
    request = _request()
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "unanswerable",
        proposition_verifier=_same_item_semantic_verdict,
    )

    assert decision.status == "supported", bundle.metadata
    assert decision.verified_citations == [identity_of(item).key]
    [derivation] = decision.typed_authority["authority_derivations"]
    assert len(derivation["premise_refs"]) == 2
    assert len(set(derivation["premise_refs"])) == 2
    assert derivation["premise_evidence_ids"] == [
        identity_of(item).key,
        identity_of(item).key,
    ]
    ref_bindings = decision.typed_authority["slot_ref_bindings"]
    assert set(ref_bindings) == {
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    }
    assert ref_bindings["support:left_subject"] != ref_bindings["support:right_subject"]
    assert (
        request.query_plan.constraints["boolean_support_group"]["distinctness_basis"]
        == "evidence_ref"
    )


def test_semantic_derivation_identity_binds_each_premise_slot_contribution() -> None:
    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_premises()),
        "yes",
        proposition_verifier=_semantic_verdict,
    )
    [derivation] = deepcopy(decision.typed_authority["authority_derivations"])
    contributions = derivation["premise_contributions"]
    contributions[0]["supports_slot_ids"] = [
        "support:proposition",
        "support:right_subject",
    ]
    contributions[1]["supports_slot_ids"] = [
        "support:proposition",
        "support:left_subject",
    ]

    assert (
        boolean_derivation_contract_status(
            derivation,
            decision.typed_authority["authority_atoms"],
            question=QUESTION,
            canonical_polarity="yes",
        )
        == "derivation_identity_mismatch"
    )


def test_poor_slot_projection_cannot_be_resolved_without_a_candidate() -> None:
    request = _request()
    generated = False
    semantic_paraphrases = [
        _item("cross-lingual", "Transfer was evaluated across two languages."),
        _item(
            "single-language",
            "The experiment also included monolingual baselines for comparison.",
        ),
    ]

    def generate(*_args: Any) -> str:
        nonlocal generated
        generated = True
        return "unanswerable"

    execution = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": semantic_paraphrases},
        generate=generate,
        proposition_verifier=_semantic_verdict,
    )

    assert execution.answer != "yes"
    assert execution.verify_decision.status == "unknown"
    assert (
        execution.verify_decision.reason == "Structured Boolean candidate was invalid."
    )
    assert execution.retrieve_decision.status != "good"
    assert generated is False
