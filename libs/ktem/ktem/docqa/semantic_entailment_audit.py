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
from .semantic_entailment_audit_support import as_int as _as_int
from .semantic_entailment_audit_support import mapping_digest as _mapping_digest
from .semantic_entailment_audit_support import text_digest as _text_digest
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
    constraint = dict(
        independent_semantic_constraint
        or semantic_relation_evidence_set_constraint(
            premises,
            proposition,
            verdict,
            auditor_relationship=auditor_relationship,
        )
    )
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
        "premise_checks": _audited_premise_checks(
            premises,
            audit_result=audit_result,
            proposition=proposition,
        ),
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "polarity_contradiction_check": polarity_contradiction_check(
            conclusion,
            premises,
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


def _audited_premise_checks(
    premises: Sequence[Mapping[str, Any]],
    *,
    audit_result: Mapping[str, Any],
    proposition: QuestionProposition,
) -> list[dict[str, Any]]:
    model_checks = audit_result.get("premise_checks") or []
    local_reason = semantic_premise_proof_span_reason(premises, proposition)
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
) -> dict[str, Any]:
    declared_slots = [
        str(slot) for slot in premise.get("binds_proposition_slots") or []
    ]
    local_slots = local_proposition_slot_checks(premise, proposition)
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
        audit, premises, proposition, verdict, relationship
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
) -> tuple[dict[str, Any] | None, str]:
    expected = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        verdict,
        auditor_relationship=relationship,
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
        or polarity_contradiction_check_validation_reason(
            audit.get("polarity_contradiction_check"),
            conclusion,
            premises,
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
    *,
    expected_constraint: Mapping[str, Any],
) -> str:
    raw_checks = audit.get("premise_checks")
    if not isinstance(raw_checks, list) or len(raw_checks) != len(premises):
        return "semantic_entailment_premise_audit_incomplete"
    analyses = list(expected_constraint.get("premise_analyses") or [])
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
        declared_slots = [
            str(slot) for slot in premise.get("binds_proposition_slots") or []
        ]
        raw_declared = check.get("declared_proposition_slots")
        raw_slot_checks = check.get("proposition_slot_checks")
        analysis = analyses[index - 1] if index <= len(analyses) else {}
        expected_slot_evidence = (
            dict(analysis.get("slot_evidence") or {})
            if isinstance(analysis, Mapping)
            else {}
        )
        if (
            raw_declared != declared_slots
            or not isinstance(raw_slot_checks, list)
            or [
                str(slot_check.get("slot"))
                for slot_check in raw_slot_checks
                if isinstance(slot_check, Mapping)
            ]
            != declared_slots
            or any(
                not isinstance(slot_check, Mapping)
                or set(slot_check)
                != {
                    "slot",
                    "binding_valid",
                    "evidence_ref",
                    "evidence_text",
                    "span_start",
                    "span_end",
                    "clause_ref",
                    "clause_start",
                    "clause_end",
                }
                or slot_check.get("binding_valid") is not True
                or not _slot_check_matches_local_span(
                    slot_check,
                    expected_slot_evidence.get(str(slot_check.get("slot") or "")),
                    premise_index=index,
                )
                for slot_check in raw_slot_checks
            )
        ):
            return "semantic_entailment_premise_audit_invalid"
    return ""


def _slot_check_matches_local_span(
    slot_check: Mapping[str, Any],
    expected: Any,
    *,
    premise_index: int,
) -> bool:
    if not isinstance(expected, Mapping):
        return False
    slot = str(slot_check.get("slot") or "")
    return bool(
        slot_check.get("evidence_ref") == f"P{premise_index}:{slot}"
        and slot_check.get("evidence_text") == expected.get("text")
        and _as_int(slot_check.get("span_start")) == _as_int(expected.get("span_start"))
        and _as_int(slot_check.get("span_end")) == _as_int(expected.get("span_end"))
        and slot_check.get("clause_ref") == expected.get("clause_ref")
        and _as_int(slot_check.get("clause_start"))
        == _as_int(expected.get("clause_start"))
        and _as_int(slot_check.get("clause_end")) == _as_int(expected.get("clause_end"))
        and str(slot_check.get("evidence_text") or "").strip()
    )


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
            or not isinstance(check.get("declared_proposition_slots"), list)
            or not check.get("declared_proposition_slots")
            or not isinstance(check.get("proposition_slot_checks"), list)
            or len(check.get("proposition_slot_checks") or [])
            != len(check.get("declared_proposition_slots") or [])
            or any(
                not isinstance(slot_check, Mapping)
                or slot_check.get("binding_valid") is not True
                or not str(slot_check.get("evidence_text") or "").strip()
                for slot_check in check.get("proposition_slot_checks") or []
            )
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
