from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_AUDITOR_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
)
from .canonical_serialization import canonical_projection_digest_trace
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
from .semantic_entailment_audit_result_validation import (
    premise_audit_validation_reason as _premise_audit_validation_reason,
)
from .semantic_entailment_audit_result_validation import (
    verified_audit_result as _verified_audit_result,
)
from .semantic_entailment_audit_support import as_int as _as_int
from .semantic_entailment_audit_support import mapping_digest as _mapping_digest
from .semantic_entailment_audit_support import text_digest as _text_digest
from .semantic_entailment_audit_support import validated_auditor as _validated_auditor
from .semantic_premise_proof_validation import (
    local_proposition_slot_checks,
    semantic_premise_proof_span_reason,
)
from .semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
    semantic_relation_evidence_set_constraint,
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
    independent_semantic_constraint: Mapping[str, Any] | None = None,
    canonical_plan_projection: Any | None = None,
) -> dict[str, Any]:
    """Create the verified audit record after every audit check passed."""

    proposition = proposition or build_question_proposition(question)
    conclusion = conclusion or typed_conclusion(proposition, verdict)
    audit_result = _verified_audit_result(audit_result, len(premises))
    conclusion_check = dict(audit_result.get("conclusion_check") or {})
    resolved_proof_mode = (
        canonical_plan_projection.proof_mode
        if canonical_plan_projection is not None
        else proof_mode
        or ("atomic_semantic" if len(premises) == 1 else "composite_conjunction")
    )
    question_payload = proposition.as_dict()
    conclusion_payload = conclusion.as_dict()
    constraint = dict(
        independent_semantic_constraint
        or semantic_relation_evidence_set_constraint(
            premises,
            proposition,
            verdict,
            auditor_relationship=auditor_relationship,
            canonical_plan_projection=canonical_plan_projection,
        )
    )
    return _semantic_audit_attestation_payload(
        question,
        verdict,
        premises,
        model=model,
        seed=seed,
        proof_mode=resolved_proof_mode,
        proposition_payload=question_payload,
        conclusion_payload=conclusion_payload,
        premise_checks=_audited_premise_checks(
            premises,
            audit_result=audit_result,
            proposition=proposition,
            canonical_plan_projection=canonical_plan_projection,
        ),
        conclusion=conclusion,
        conclusion_check=conclusion_check,
        auditor_relationship=auditor_relationship,
        constraint=constraint,
        canonical_plan_projection=canonical_plan_projection,
    )


def _semantic_audit_attestation_payload(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    *,
    model: str,
    seed: int,
    proof_mode: str,
    proposition_payload: Mapping[str, Any],
    conclusion_payload: Mapping[str, Any],
    premise_checks: list[dict[str, Any]],
    conclusion: TypedConclusion,
    conclusion_check: Mapping[str, Any],
    auditor_relationship: str,
    constraint: Mapping[str, Any],
    canonical_plan_projection: Any | None,
) -> dict[str, Any]:
    result = {
        "contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "status": "verified",
        "proposal_digest": semantic_entailment_proposal_digest(
            question,
            verdict,
            premises,
            proof_mode=proof_mode,
            question_proposition=proposition_payload,
            typed_conclusion_value=conclusion_payload,
        ),
        "verdict": verdict,
        "proof_mode": proof_mode,
        "question_proposition": proposition_payload,
        "typed_conclusion": conclusion_payload,
        "premise_count": len(premises),
        "premise_checks": premise_checks,
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "polarity_contradiction_check": _polarity_check(
            conclusion,
            premises,
            canonical_plan_projection=canonical_plan_projection,
        ),
        "independent_semantic_constraint": constraint,
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
    if canonical_plan_projection is not None:
        projection_trace = canonical_projection_digest_trace(canonical_plan_projection)
        result.update(
            {
                "canonical_evidence_plan_id": canonical_plan_projection.plan_id,
                "canonical_plan_digest": canonical_plan_projection.plan_digest,
                "canonical_projection_digest": projection_trace["validator_digest"],
                "canonical_projection_digest_trace": projection_trace,
            }
        )
    return result


def _audited_premise_checks(
    premises: Sequence[Mapping[str, Any]],
    *,
    audit_result: Mapping[str, Any],
    proposition: QuestionProposition,
    canonical_plan_projection: Any | None = None,
) -> list[dict[str, Any]]:
    model_checks = audit_result.get("premise_checks") or []
    local_reason = semantic_premise_proof_span_reason(
        premises,
        proposition,
        canonical_plan_projection=canonical_plan_projection,
    )
    return [
        _audited_premise_check(
            premise_index=index,
            premise=premise,
            model_check=(
                model_checks[index - 1]
                if index <= len(model_checks)
                and isinstance(model_checks[index - 1], Mapping)
                else {}
            ),
            proposition=proposition,
            local_reason=local_reason,
            canonical_plan_projection=canonical_plan_projection,
        )
        for index, premise in enumerate(premises, start=1)
    ]


def _audited_premise_check(
    *,
    premise_index: int,
    premise: Mapping[str, Any],
    model_check: Mapping[str, Any],
    proposition: QuestionProposition,
    local_reason: str,
    canonical_plan_projection: Any | None = None,
) -> dict[str, Any]:
    declared_slots = [
        str(slot) for slot in premise.get("binds_proposition_slots") or []
    ]
    local_slots = local_proposition_slot_checks(
        premise,
        proposition,
        canonical_plan_projection=canonical_plan_projection,
    )
    if canonical_plan_projection is not None:
        local_evidence = dict(
            canonical_plan_projection.audit_slot_evidence.get(f"P{premise_index}", {})
        )
    else:
        local_analysis = semantic_relation_clause_analysis(premise, proposition)
        local_evidence = dict(local_analysis.get("slot_evidence") or {})
    model_slots = {
        str(slot_check.get("slot")): slot_check
        for slot_check in model_check.get("proposition_slot_checks") or []
        if isinstance(slot_check, Mapping)
    }
    slot_checks = []
    for slot in declared_slots:
        model_slot = model_slots.get(slot, {})
        expected = local_evidence.get(slot)
        expected = expected if isinstance(expected, Mapping) else {}
        slot_check = {
            "slot": slot,
            "binding_valid": local_slots.get(slot, False)
            and model_slot.get("binding_valid") is True,
            "evidence_ref": f"P{premise_index}:{slot}",
            "evidence_text": str(expected.get("text") or ""),
            "span_start": _as_int(expected.get("span_start")),
            "span_end": _as_int(expected.get("span_end")),
            "clause_ref": str(expected.get("clause_ref") or ""),
            "clause_start": _as_int(expected.get("clause_start")),
            "clause_end": _as_int(expected.get("clause_end")),
        }
        slot_checks.append(slot_check)
    binding_valid = bool(slot_checks) and all(
        value["binding_valid"] for value in slot_checks
    )
    if local_reason and not declared_slots:
        binding_valid = False
    return {
        "premise_index": premise_index,
        "evidence_id": str(premise.get("evidence_id") or ""),
        "quote_digest": _text_digest(str(premise.get("quote") or "")),
        "fragment_digest": _text_digest(str(premise.get("proposition_fragment") or "")),
        "fragment_entailed": model_check.get("fragment_entailed") is True,
        "scope_consistent": model_check.get("scope_consistent") is True,
        "proposition_bindings_valid": binding_valid,
        "evidence_relation_valid": model_check.get("evidence_relation_valid") is True,
        "declared_proposition_slots": declared_slots,
        "proposition_slot_checks": slot_checks,
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
    canonical_plan_projection: Any | None = None,
) -> str:
    """Return an empty reason only for a complete, proposal-bound audit."""

    if not isinstance(audit, Mapping):
        return "semantic_entailment_audit_missing"
    expected_proof_mode = proof_mode or (
        "atomic_semantic" if len(premises) == 1 else "composite_conjunction"
    )
    proposition = proposition or build_question_proposition(question)
    conclusion = conclusion or typed_conclusion(proposition, verdict)
    premise_reason = semantic_premise_proof_span_reason(
        premises,
        proposition,
        audit_result=audit,
        canonical_plan_projection=canonical_plan_projection,
    )
    if premise_reason:
        return premise_reason
    if _audit_binding_invalid(
        audit,
        question=question,
        verdict=verdict,
        premises=premises,
        proof_mode=expected_proof_mode,
        proposition=proposition,
        conclusion=conclusion,
        canonical_plan_projection=canonical_plan_projection,
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
    expected_constraint, constraint_reason = _validated_semantic_constraint(
        audit,
        premises,
        proposition,
        verdict,
        relationship,
        canonical_plan_projection=canonical_plan_projection,
    )
    if constraint_reason:
        return constraint_reason
    conclusion_reason = _bound_conclusion_audit_reason(
        audit,
        auditor,
        question=question,
        verdict=verdict,
        premises=premises,
        proposition=proposition,
        conclusion=conclusion,
        relationship=relationship,
        release_mode=release_mode,
        canonical_plan_projection=canonical_plan_projection,
    )
    if conclusion_reason:
        return conclusion_reason
    assert expected_constraint is not None
    return _premise_audit_validation_reason(
        audit,
        premises,
        expected_constraint=expected_constraint,
    )


def _validated_semantic_constraint(
    audit: Mapping[str, Any],
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    verdict: str,
    relationship: str,
    canonical_plan_projection: Any | None = None,
) -> tuple[dict[str, Any] | None, str]:
    expected = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        verdict,
        auditor_relationship=relationship,
        canonical_plan_projection=canonical_plan_projection,
    )
    recorded = audit.get("independent_semantic_constraint")
    if not isinstance(recorded, Mapping) or dict(recorded) != expected:
        return None, "independent_semantic_constraint_binding_invalid"
    if expected.get("status") != "passed":
        return None, str(
            expected.get("reason") or "independent_semantic_constraint_rejected"
        )
    return expected, ""


def _bound_conclusion_audit_reason(
    audit: Mapping[str, Any],
    auditor: Mapping[str, Any],
    *,
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
    relationship: str,
    release_mode: bool,
    canonical_plan_projection: Any | None = None,
) -> str:
    conclusion_audit = audit.get("conclusion_audit")
    conclusion_audit = conclusion_audit if isinstance(conclusion_audit, Mapping) else {}
    if (
        conclusion_audit.get("auditor_relationship") != relationship
        or conclusion_audit.get("model") != auditor.get("model")
        or _as_int(conclusion_audit.get("seed")) != _as_int(auditor.get("seed"))
    ):
        return "conclusion_audit_auditor_binding_invalid"
    return (
        validate_question_proposition(audit.get("question_proposition"), question)
        or validate_typed_conclusion(
            audit.get("typed_conclusion"), proposition, verdict
        )
        or conclusion_audit_validation_reason(
            conclusion_audit,
            conclusion,
            release_mode=release_mode,
        )
        or _polarity_check_validation_reason(
            audit.get("polarity_contradiction_check"),
            conclusion,
            premises,
            canonical_plan_projection=canonical_plan_projection,
        )
    )


def _audit_binding_invalid(
    audit: Mapping[str, Any],
    *,
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    proof_mode: str,
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
    canonical_plan_projection: Any | None = None,
) -> bool:
    invalid = bool(
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
    if canonical_plan_projection is not None:
        projection_trace = canonical_projection_digest_trace(canonical_plan_projection)
        invalid = invalid or any(
            audit.get(field) != expected
            for field, expected in (
                ("canonical_evidence_plan_id", canonical_plan_projection.plan_id),
                ("canonical_plan_digest", canonical_plan_projection.plan_digest),
                (
                    "canonical_projection_digest",
                    projection_trace["validator_digest"],
                ),
            )
        )
        invalid = invalid or (
            isinstance(audit.get("canonical_projection_digest_trace"), Mapping)
            and audit["canonical_projection_digest_trace"].get("status") == "mismatch"
        )
    return invalid


def _polarity_check(
    conclusion: TypedConclusion,
    premises: Sequence[Mapping[str, Any]],
    *,
    canonical_plan_projection: Any | None = None,
) -> dict[str, Any]:
    if canonical_plan_projection is None:
        return polarity_contradiction_check(conclusion, premises)
    observed_polarity = (
        "yes"
        if canonical_plan_projection.polarity_relation == "proposition_support"
        else "no"
    )
    opposite = "no" if conclusion.polarity == "yes" else "yes"
    status = (
        "contradiction_detected"
        if observed_polarity == opposite
        else "aligned"
        if observed_polarity == conclusion.polarity
        else "no_explicit_contradiction"
    )
    return {
        "contract_id": "polarity_contradiction_check.v1",
        "conclusion_id": conclusion.conclusion_id,
        "status": status,
        "observed_polarities": [observed_polarity] * len(premises),
        "quote_digests": [
            _text_digest(str(premise.get("quote") or "")) for premise in premises
        ],
        "method": "frozen_canonical_proposition_plan_projection",
        "independent_from_models": True,
    }


def _polarity_check_validation_reason(
    value: Any,
    conclusion: TypedConclusion,
    premises: Sequence[Mapping[str, Any]],
    *,
    canonical_plan_projection: Any | None = None,
) -> str:
    if canonical_plan_projection is None:
        return polarity_contradiction_check_validation_reason(
            value,
            conclusion,
            premises,
        )
    expected = _polarity_check(
        conclusion,
        premises,
        canonical_plan_projection=canonical_plan_projection,
    )
    if not isinstance(value, Mapping) or dict(value) != expected:
        return "polarity_contradiction_check_binding_invalid"
    if value.get("status") == "contradiction_detected":
        return "polarity_contradiction_detected"
    return ""
