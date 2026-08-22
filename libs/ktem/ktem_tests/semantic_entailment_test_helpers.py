from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authority_schema import GROUNDED_SEMANTIC_VERIFIER_CONTRACT
from ktem.docqa.question_proposition import build_question_proposition, typed_conclusion
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
    conclusion = typed_conclusion(proposition, response["verdict"])
    response["question_proposition"] = proposition.as_dict()
    response["typed_conclusion"] = conclusion.as_dict()
    offsets: dict[str, int] = {}
    for index, premise in enumerate(response["premises"], start=1):
        evidence_id = str(premise["evidence_id"])
        start = offsets.get(evidence_id, 0)
        quote = str(premise["quote"])
        premise.setdefault("span_selector", f"test:{evidence_id}:S{index}")
        premise.setdefault("span_start", start)
        premise.setdefault("span_end", start + len(quote))
        offsets[evidence_id] = start + len(quote) + 1
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
        audit_result={
            "premise_checks": [
                {
                    "premise_ref": f"P{index}",
                    "fragment_entailed": True,
                    "scope_consistent": True,
                }
                for index in range(1, len(response["premises"]) + 1)
            ],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        },
    )
    return response
