from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_AUDITOR_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
)
from .conclusion_audit import (
    conclusion_audit_attestation,
    conclusion_audit_validation_reason,
)
from .polarity_contradiction_check import (
    polarity_contradiction_check,
    polarity_contradiction_check_validation_reason,
)
from .question_proposition import (
    QuestionProposition,
    TypedConclusion,
    build_question_proposition,
    typed_conclusion,
    validate_question_proposition,
    validate_typed_conclusion,
)


def semantic_entailment_proposal_digest(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    *,
    proof_mode: str = "",
    question_proposition: Mapping[str, Any] | None = None,
    typed_conclusion_value: Mapping[str, Any] | None = None,
) -> str:
    """Bind an entailment audit to the exact proposed proof transaction."""

    payload = {
        "question": str(question or "").strip(),
        "verdict": str(verdict or ""),
        "proof_mode": proof_mode,
        "question_proposition": dict(question_proposition or {}),
        "typed_conclusion": dict(typed_conclusion_value or {}),
        "premises": [
            {
                "evidence_id": str(value.get("evidence_id") or ""),
                "quote": str(value.get("quote") or ""),
                "proposition_fragment": str(value.get("proposition_fragment") or ""),
                "supports_slot_ids": sorted(
                    str(slot_id) for slot_id in value.get("supports_slot_ids") or []
                ),
                "binds_proposition_slots": sorted(
                    str(slot_id)
                    for slot_id in value.get("binds_proposition_slots") or []
                ),
                "proposition_slot_bindings": {
                    str(slot): str(binding)
                    for slot, binding in sorted(
                        dict(value.get("proposition_slot_bindings") or {}).items()
                    )
                },
                "evidence_relation": str(value.get("evidence_relation") or ""),
            }
            for value in premises
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_entailment_audit_attestation(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    *,
    model: str,
    seed: int,
    proof_mode: str = "",
    proposition: QuestionProposition | None = None,
    conclusion: TypedConclusion | None = None,
    auditor_relationship: str = "same_instance",
    audit_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the verified audit record after every audit check passed."""

    proposition = proposition or build_question_proposition(question)
    conclusion = conclusion or typed_conclusion(proposition, verdict)
    audit_result = _verified_audit_result(audit_result, len(premises))
    conclusion_check = dict(audit_result.get("conclusion_check") or {})
    resolved_proof_mode = proof_mode or (
        "atomic_semantic" if len(premises) == 1 else "composite_conjunction"
    )
    question_payload = proposition.as_dict()
    conclusion_payload = conclusion.as_dict()
    return {
        "contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "status": "verified",
        "proposal_digest": semantic_entailment_proposal_digest(
            question,
            verdict,
            premises,
            proof_mode=resolved_proof_mode,
            question_proposition=question_payload,
            typed_conclusion_value=conclusion_payload,
        ),
        "verdict": verdict,
        "proof_mode": resolved_proof_mode,
        "question_proposition": question_payload,
        "typed_conclusion": conclusion_payload,
        "premise_count": len(premises),
        "premise_checks": _audited_premise_checks(premises),
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "polarity_contradiction_check": polarity_contradiction_check(
            conclusion,
            premises,
        ),
        "auditor": {
            "contract_id": GROUNDED_SEMANTIC_AUDITOR_CONTRACT,
            "model": str(model or ""),
            "seed": seed,
            "relationship": auditor_relationship,
        },
        "conclusion_audit": conclusion_audit_attestation(
            conclusion,
            conclusion_check,
            auditor_relationship=auditor_relationship,
            model=model,
            seed=seed,
        ),
    }


def _audited_premise_checks(
    premises: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "premise_index": index,
            "evidence_id": str(premise.get("evidence_id") or ""),
            "quote_digest": _text_digest(str(premise.get("quote") or "")),
            "fragment_digest": _text_digest(
                str(premise.get("proposition_fragment") or "")
            ),
            "fragment_entailed": True,
            "scope_consistent": True,
            "proposition_bindings_valid": True,
            "evidence_relation_valid": True,
            "proposition_binding_digest": _mapping_digest(
                {
                    str(slot): str(binding)
                    for slot, binding in dict(
                        premise.get("proposition_slot_bindings") or {}
                    ).items()
                }
            ),
            "evidence_relation": str(premise.get("evidence_relation") or ""),
        }
        for index, premise in enumerate(premises, start=1)
    ]


def semantic_entailment_audit_validation_reason(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    audit: Any,
    *,
    proof_mode: str = "",
    proposition: QuestionProposition | None = None,
    conclusion: TypedConclusion | None = None,
    release_mode: bool = False,
) -> str:
    """Return an empty reason only for a complete, proposal-bound audit."""

    if not isinstance(audit, Mapping):
        return "semantic_entailment_audit_missing"
    expected_proof_mode = proof_mode or (
        "atomic_semantic" if len(premises) == 1 else "composite_conjunction"
    )
    proposition = proposition or build_question_proposition(question)
    conclusion = conclusion or typed_conclusion(proposition, verdict)
    if _audit_binding_invalid(
        audit,
        question=question,
        verdict=verdict,
        premises=premises,
        proof_mode=expected_proof_mode,
        proposition=proposition,
        conclusion=conclusion,
    ):
        return "semantic_entailment_audit_binding_invalid"
    if (
        audit.get("jointly_entails") is not True
        or audit.get("each_premise_required") is not True
        or audit.get("contradiction_free") is not True
    ):
        return "semantic_entailment_audit_verdict_invalid"
    auditor, auditor_reason = _validated_auditor(audit, release_mode=release_mode)
    if auditor_reason:
        return auditor_reason
    relationship = str(auditor.get("relationship") or "")
    conclusion_audit = audit.get("conclusion_audit")
    conclusion_audit = conclusion_audit if isinstance(conclusion_audit, Mapping) else {}
    if (
        conclusion_audit.get("auditor_relationship") != relationship
        or conclusion_audit.get("model") != auditor.get("model")
        or _as_int(conclusion_audit.get("seed")) != _as_int(auditor.get("seed"))
    ):
        return "conclusion_audit_auditor_binding_invalid"
    question_reason = validate_question_proposition(
        audit.get("question_proposition"), question
    )
    if question_reason:
        return question_reason
    conclusion_reason = validate_typed_conclusion(
        audit.get("typed_conclusion"), proposition, verdict
    )
    if conclusion_reason:
        return conclusion_reason
    conclusion_audit_reason = conclusion_audit_validation_reason(
        conclusion_audit,
        conclusion,
        release_mode=release_mode,
    )
    if conclusion_audit_reason:
        return conclusion_audit_reason
    contradiction_reason = polarity_contradiction_check_validation_reason(
        audit.get("polarity_contradiction_check"),
        conclusion,
        premises,
    )
    if contradiction_reason:
        return contradiction_reason
    return _premise_audit_validation_reason(audit, premises)


def _audit_binding_invalid(
    audit: Mapping[str, Any],
    *,
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    proof_mode: str,
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
) -> bool:
    return bool(
        audit.get("contract_id") != SEMANTIC_ENTAILMENT_AUDIT_CONTRACT
        or audit.get("status") != "verified"
        or audit.get("verdict") != verdict
        or _as_int(audit.get("premise_count")) != len(premises)
        or audit.get("proof_mode") != proof_mode
        or audit.get("proposal_digest")
        != semantic_entailment_proposal_digest(
            question,
            verdict,
            premises,
            proof_mode=proof_mode,
            question_proposition=proposition.as_dict(),
            typed_conclusion_value=conclusion.as_dict(),
        )
    )


def _validated_auditor(
    audit: Mapping[str, Any],
    *,
    release_mode: bool,
) -> tuple[Mapping[str, Any], str]:
    auditor = audit.get("auditor")
    if not isinstance(auditor, Mapping) or (
        auditor.get("contract_id") != GROUNDED_SEMANTIC_AUDITOR_CONTRACT
        or not str(auditor.get("model") or "").strip()
    ):
        return {}, "semantic_entailment_auditor_attestation_invalid"
    relationship = str(auditor.get("relationship") or "")
    if relationship not in {
        "same_instance",
        "distinct_instance_same_model",
        "distinct_model",
    }:
        return {}, "semantic_entailment_auditor_attestation_invalid"
    if release_mode and relationship == "same_instance":
        return {}, "release_conclusion_auditor_not_independent"
    return auditor, ""


def _premise_audit_validation_reason(
    audit: Mapping[str, Any],
    premises: Sequence[Mapping[str, Any]],
) -> str:
    raw_checks = audit.get("premise_checks")
    if not isinstance(raw_checks, list) or len(raw_checks) != len(premises):
        return "semantic_entailment_premise_audit_incomplete"
    for index, (check, premise) in enumerate(zip(raw_checks, premises), start=1):
        if not isinstance(check, Mapping) or (
            _as_int(check.get("premise_index")) != index
            or check.get("evidence_id") != str(premise.get("evidence_id") or "")
            or check.get("quote_digest")
            != _text_digest(str(premise.get("quote") or ""))
            or check.get("fragment_digest")
            != _text_digest(str(premise.get("proposition_fragment") or ""))
            or check.get("fragment_entailed") is not True
            or check.get("scope_consistent") is not True
            or check.get("proposition_bindings_valid") is not True
            or check.get("evidence_relation_valid") is not True
            or check.get("proposition_binding_digest")
            != _mapping_digest(
                {
                    str(slot): str(binding)
                    for slot, binding in dict(
                        premise.get("proposition_slot_bindings") or {}
                    ).items()
                }
            )
            or check.get("evidence_relation")
            != str(premise.get("evidence_relation") or "")
        ):
            return "semantic_entailment_premise_audit_invalid"
    return ""


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verified_audit_result(
    audit_result: Mapping[str, Any],
    premise_count: int,
) -> dict[str, Any]:
    value = dict(audit_result)
    checks = value.get("premise_checks")
    conclusion = value.get("conclusion_check")
    if (
        not isinstance(checks, list)
        or len(checks) != premise_count
        or any(
            not isinstance(check, Mapping)
            or check.get("fragment_entailed") is not True
            or check.get("scope_consistent") is not True
            or check.get("proposition_bindings_valid") is not True
            or check.get("evidence_relation_valid") is not True
            for check in checks
        )
        or value.get("jointly_entails") is not True
        or value.get("each_premise_required") is not True
        or value.get("contradiction_free") is not True
        or not isinstance(conclusion, Mapping)
        or any(
            conclusion.get(field) is not True
            for field in (
                "conclusion_entailed",
                "actor_consistent",
                "predicate_consistent",
                "object_consistent",
                "polarity_consistent",
                "quantifier_consistent",
                "scope_consistent",
            )
        )
    ):
        raise ValueError(
            "A verified attestation requires a fully passing audit result."
        )
    return value


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _mapping_digest(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
