from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .boolean_authority_derivation import (
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from .boolean_authority_schema import (
    SEMANTIC_EVIDENCE_SET_RULE,
    BooleanAuthorityDerivation,
    BooleanEvidenceAuthority,
)
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_relations import primary_boolean_relation
from .boolean_scope_quantifiers import _closed_quantifier
from .question_proposition import build_question_proposition
from .semantic_relation_clause_validation import (
    frozen_semantic_relation_analyses,
    semantic_relation_clause_analysis,
    semantic_required_argument_tokens,
    semantic_slot_evidence_projection,
    validated_argument_tokens,
)


def semantic_evidence_set_derivation(
    question: str,
    verdict: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    attestation: dict[str, Any],
    *,
    slot_support: dict[str, tuple[str, ...]],
    canonical_plan_projection: Any | None = None,
) -> BooleanAuthorityDerivation:
    relation = primary_boolean_relation(question) or "entails"
    required = (
        tuple(canonical_plan_projection.required_object_tokens)
        if canonical_plan_projection is not None
        else semantic_required_argument_tokens(question)
    )
    conclusion = _typed_derivation_conclusion(
        question,
        verdict,
        relation,
        required,
        premises,
        attestation,
    )
    contributions = _premise_contributions(
        question,
        premises,
        slot_support,
        required=required,
        canonical_plan_projection=canonical_plan_projection,
        evidence_relation=str(attestation.get("verdict") or verdict),
    )
    covered = tuple(
        sorted(
            {
                token
                for contribution in contributions
                for token in contribution["argument_tokens"]
            }
        )
    )
    identity = boolean_derivation_identity_payload(
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        support_mode="evidence_set",
        verifier_attestation=attestation,
        premise_contributions=contributions,
    )
    return BooleanAuthorityDerivation(
        derivation_id=boolean_derivation_id(identity),
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        premise_evidence_ids=tuple(value.evidence_id for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        covered_argument_tokens=covered,
        premise_contributions=contributions,
        support_mode="evidence_set",
        verifier_attestation=attestation,
    )


def _typed_derivation_conclusion(
    question: str,
    verdict: str,
    relation: str,
    required: tuple[str, ...],
    premises: tuple[BooleanEvidenceAuthority, ...],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    fallback_object = (
        " ".join(required)
        if required != ("complete_proposition",)
        else question.strip()
    )
    actors = {value.actor for value in premises}
    scopes = {value.section_scope for value in premises}
    typed = attestation.get("typed_conclusion") or {}
    object_value = str(
        typed.get("object_surface") or typed.get("object_type") or fallback_object
    )
    return {
        "contract_id": str(typed.get("contract_id") or "typed_conclusion.v1"),
        "conclusion_id": str(typed.get("conclusion_id") or ""),
        "proposition_id": str(typed.get("proposition_id") or ""),
        "actor": str(typed.get("actor") or "")
        or (next(iter(actors)) if len(actors) == 1 else "current_source"),
        "predicate": str(typed.get("predicate") or relation),
        "relation": str(typed.get("predicate") or relation),
        "object": object_value,
        "object_role": str(typed.get("object_role") or "object"),
        "subject_surface": str(typed.get("subject_surface") or ""),
        "object_surface": str(typed.get("object_surface") or ""),
        "arguments": [object_value],
        "polarity": verdict,
        "qualifier": str(typed.get("qualifier") or proposition_qualifier(question)),
        "quantifier": str(typed.get("quantifier") or _closed_quantifier(question)),
        "modality": str(typed.get("modality") or "asserted"),
        "negated": bool(typed.get("negated")),
        "time_scope": str(typed.get("time_scope") or "unspecified"),
        "scope": str(typed.get("scope") or "")
        or (next(iter(scopes)) if len(scopes) == 1 else "document"),
        "section_scope": next(iter(scopes)) if len(scopes) == 1 else "document",
        "surface": str(typed.get("surface") or question.strip()),
    }


def _premise_contributions(
    question: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    slot_support: dict[str, tuple[str, ...]],
    *,
    required: tuple[str, ...],
    canonical_plan_projection: Any | None = None,
    evidence_relation: str = "",
) -> tuple[dict[str, Any], ...]:
    if canonical_plan_projection is not None:
        return _frozen_premise_contributions(
            premises,
            slot_support,
            projection=canonical_plan_projection,
            evidence_relation=evidence_relation,
        )
    return _legacy_premise_contributions(
        question,
        premises,
        slot_support,
        required=required,
    )


def _frozen_premise_contributions(
    premises: tuple[BooleanEvidenceAuthority, ...],
    slot_support: dict[str, tuple[str, ...]],
    *,
    projection: Any,
    evidence_relation: str,
) -> tuple[dict[str, Any], ...]:
    analyses = frozen_semantic_relation_analyses(projection, evidence_relation)
    contributions = []
    for index, premise in enumerate(premises, start=1):
        expected = _frozen_authority_premise(premise, projection)
        if expected is None or index > len(analyses):
            continue
        selector = str(expected.get("span_selector") or "")
        slot_evidence = {
            slot: {
                **dict(span),
                "evidence_ref": (
                    f"{premise.evidence_ref}#slot:{slot}:"
                    f"{span.get('span_start')}:{span.get('span_end')}"
                ),
            }
            for slot, span in projection.slot_evidence.get(selector, {}).items()
        }
        contributions.append(
            _premise_contribution(
                premise,
                index=index,
                slot_support=slot_support,
                analysis=analyses[index - 1],
                argument_tokens=list(
                    projection.covered_tokens_by_ref.get(selector, ())
                ),
                binds_slots=list(expected.get("binds_proposition_slots") or []),
                proposition_bindings=dict(
                    expected.get("proposition_slot_bindings") or {}
                ),
                slot_evidence=slot_evidence,
            )
        )
    return tuple(contributions)


def _legacy_premise_contributions(
    question: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    slot_support: dict[str, tuple[str, ...]],
    *,
    required: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    proposition = build_question_proposition(question)
    contributions = []
    for index, premise in enumerate(premises, start=1):
        binds_slots = [slot for slot, _value in premise.proposition_slot_bindings]
        analysis = semantic_relation_clause_analysis(
            {
                "quote": premise.quote,
                "binds_proposition_slots": binds_slots,
                "proposition_slot_bindings": dict(premise.proposition_slot_bindings),
                "evidence_relation": premise.evidence_relation,
            },
            proposition,
        )
        span_base = (
            premise.canonical_start
            if premise.canonical_start is not None
            else premise.span_start
        )
        contributions.append(
            _premise_contribution(
                premise,
                index=index,
                slot_support=slot_support,
                analysis=analysis,
                argument_tokens=list(
                    validated_argument_tokens(question, analysis, required)
                ),
                binds_slots=binds_slots,
                proposition_bindings=dict(premise.proposition_slot_bindings),
                slot_evidence=semantic_slot_evidence_projection(
                    analysis,
                    premise_ref=premise.evidence_ref,
                    span_base=span_base,
                ),
            )
        )
    return tuple(contributions)


def _premise_contribution(
    premise: BooleanEvidenceAuthority,
    *,
    index: int,
    slot_support: dict[str, tuple[str, ...]],
    analysis: Mapping[str, Any],
    argument_tokens: list[str],
    binds_slots: list[str],
    proposition_bindings: dict[str, Any],
    slot_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": premise.evidence_id,
        "evidence_ref": premise.evidence_ref,
        "role": f"semantic_premise:{index}",
        "order": index,
        "argument_tokens": argument_tokens,
        "proposition_fragment": premise.object,
        "supports_slot_ids": list(slot_support[premise.evidence_ref]),
        "binds_proposition_slots": binds_slots,
        "proposition_slot_bindings": proposition_bindings,
        "proposition_slot_evidence": slot_evidence,
        "local_semantic_relation": {
            "contract_id": analysis["contract_id"],
            "status": analysis["status"],
            "evidence_relation": analysis["evidence_relation"],
            "joint_relation_clause_bound": analysis["joint_relation_clause_bound"],
            "analysis_digest": analysis["analysis_digest"],
        },
        "evidence_relation": premise.evidence_relation,
    }


def _frozen_authority_premise(
    premise: BooleanEvidenceAuthority,
    projection: Any,
) -> Mapping[str, Any] | None:
    for expected in projection.premises:
        if (
            expected.get("evidence_id") == premise.evidence_id
            and expected.get("span_start") == premise.span_start
            and expected.get("span_end") == premise.span_end
        ):
            return expected
    return None
