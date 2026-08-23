from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authority_schema import GROUNDED_SEMANTIC_VERIFIER_CONTRACT
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    build_question_proposition,
    proposition_evidence_bindings,
    typed_conclusion,
)
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation


def audited_verdict(
    response: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    """Attach a valid independent-audit attestation to a semantic test verdict."""

    proof_mode = (
        "atomic_semantic" if len(response["premises"]) == 1 else "composite_conjunction"
    )
    response["proof_mode"] = proof_mode
    proposition = build_question_proposition(question)
    canonical_bindings = proposition_evidence_bindings(proposition)
    conclusion = typed_conclusion(proposition, response["verdict"])
    evidence_relation = (
        "proposition_support"
        if response["verdict"] == "yes"
        else "explicit_contradiction"
    )
    response["evidence_relation"] = evidence_relation
    response["question_proposition"] = proposition.as_dict()
    response["typed_conclusion"] = conclusion.as_dict()
    _bind_test_premises(response["premises"], canonical_bindings, evidence_relation)
    verifier = response.setdefault("verifier", {})
    verifier.update(
        {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "release_mode": False,
            "auditor_relationship": "distinct_model",
            "semantic_pack_digest": "test-semantic-pack",
        }
    )
    response["entailment_audit"] = semantic_entailment_audit_attestation(
        question,
        response["verdict"],
        response["premises"],
        model="independent-test-auditor",
        seed=8,
        proof_mode=proof_mode,
        proposition=proposition,
        conclusion=conclusion,
        auditor_relationship="distinct_model",
        audit_result=_test_audit_result(len(response["premises"])),
    )
    return response


def _bind_test_premises(
    premises: list[dict[str, Any]],
    canonical_bindings: dict[str, str],
    evidence_relation: str,
) -> None:
    offsets: dict[str, int] = {}
    for index, premise in enumerate(premises, start=1):
        evidence_id = str(premise["evidence_id"])
        start = offsets.get(evidence_id, 0)
        quote = str(premise["quote"])
        premise.setdefault("span_selector", f"test:{evidence_id}:S{index}")
        premise.setdefault("span_start", start)
        premise.setdefault("span_end", start + len(quote))
        proposition_slots = _test_proposition_slots(index, len(premises))
        premise.setdefault("binds_proposition_slots", proposition_slots)
        premise["proposition_slot_bindings"] = {
            slot: canonical_bindings[slot]
            for slot in premise["binds_proposition_slots"]
        }
        premise["evidence_relation"] = evidence_relation
        offsets[evidence_id] = start + len(quote) + 1


def _test_proposition_slots(index: int, premise_count: int) -> list[str]:
    if premise_count == 1:
        return list(PROPOSITION_EVIDENCE_SLOTS)
    if index == 1:
        return ["actor", "predicate"]
    if index == 2:
        return ["object", "quantifier"]
    return ["object"]


def _test_audit_result(premise_count: int) -> dict[str, Any]:
    return {
        "premise_checks": [
            {
                "premise_ref": f"P{index}",
                "fragment_entailed": True,
                "scope_consistent": True,
                "proposition_bindings_valid": True,
                "evidence_relation_valid": True,
            }
            for index in range(1, premise_count + 1)
        ],
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "conclusion_check": {
            "conclusion_entailed": True,
            "actor_consistent": True,
            "predicate_consistent": True,
            "object_consistent": True,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": True,
        },
    }
