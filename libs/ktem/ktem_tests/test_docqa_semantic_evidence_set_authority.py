from __future__ import annotations

from functools import partial
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _item(evidence_id: str, text: str, *, source_id: str = "paper") -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "section_id": "experiments",
        "text": text,
    }


def _premises() -> list[dict[str, str]]:
    return [
        _item(
            "cross-lingual",
            "We evaluated transfer in the cross-lingual setting.",
        ),
        _item(
            "single-language",
            "The same experiment included single-language baselines for comparison.",
        ),
    ]


def _request() -> DocQARequest:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="general",
    )
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
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
    return {
        "contract_id": "semantic_proposition_verdict.v1",
        "verdict": "yes",
        "support_mode": "evidence_set",
        "premises": [
            {
                "evidence_id": identity_of(item).key,
                "quote": item["text"],
            }
            for item in bundle.items
        ],
        "verifier": {
            "contract_id": "grounded_semantic_verifier.v1",
            "model": "test-double",
            "seed": 7,
        },
    }


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
    assert derivation["rule_id"] == "grounded_semantic_evidence_set_entailment.v1"
    assert derivation["support_mode"] == "evidence_set"
    assert derivation["verifier_attestation"]["model"] == "test-double"
    assert set(derivation["premise_evidence_ids"]) == evidence_ids
    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert set(slot.evidence_ids) == evidence_ids


def test_semantic_verifier_cannot_bind_an_invented_quote() -> None:
    def invented_quote(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verdict = _semantic_verdict(*args, **kwargs)
        verdict["premises"][0]["quote"] = "This sentence was never retrieved."
        return verdict

    decision = verify_decision(
        _request(),
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_premises()),
        "yes",
        proposition_verifier=invented_quote,
    )

    assert decision.status != "supported"
    assert decision.verified_citations == []
    assert decision.typed_authority["state"] == "missing"


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


def test_poor_slot_projection_can_be_resolved_before_generation() -> None:
    request = _request()
    generated = False

    def generate(*_args: Any) -> str:
        nonlocal generated
        generated = True
        return "unanswerable"

    execution = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": _premises()},
        generate=generate,
        verify=partial(
            verify_decision,
            proposition_verifier=_semantic_verdict,
        ),
    )

    assert execution.answer == "yes"
    assert execution.verify_decision.status == "supported"
    assert execution.retrieve_decision.status != "good"
    assert generated is False

