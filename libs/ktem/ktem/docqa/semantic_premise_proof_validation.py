from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    QuestionProposition,
    proposition_evidence_bindings,
)
from .semantic_relation_clause_validation import semantic_relation_clause_analysis


def semantic_premise_proof_span_reason(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    *,
    audit_result: Mapping[str, Any] | None = None,
) -> str:
    canonical_bindings = proposition_evidence_bindings(proposition)
    for premise_index, premise in enumerate(premises):
        quote = " ".join(str(premise.get("quote") or "").split())
        if not _is_assertive_proof_span(quote):
            return "semantic_entailment_premise_quote_not_proof"
        fragment = " ".join(str(premise.get("proposition_fragment") or "").split())
        if not fragment or re.match(r"^#{1,6}\s+", fragment):
            return "semantic_entailment_premise_quote_not_proof"
        raw_slots = premise.get("binds_proposition_slots")
        raw_bindings = premise.get("proposition_slot_bindings")
        if not _valid_binding_shape(raw_slots, raw_bindings, canonical_bindings):
            return "semantic_entailment_proposition_binding_unbound"
        assert isinstance(raw_slots, list)
        declared_slots = [str(slot) for slot in raw_slots]
        if "actor" in declared_slots and _is_model_declaration(quote):
            return "semantic_entailment_premise_quote_not_proof"
        reason = _audit_slot_evidence_reason(
            premise_index,
            declared_slots,
            quote,
            audit_result,
            premise=premise,
            proposition=proposition,
        )
        if reason:
            return reason
    return ""


def semantic_entailment_premise_validation_reason(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    *,
    audit_result: Mapping[str, Any] | None = None,
) -> str:
    """Validate exact proof spans and model slot evidence before attestation."""

    return semantic_premise_proof_span_reason(
        premises,
        proposition,
        audit_result=audit_result,
    )


def local_proposition_slot_checks(
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
) -> dict[str, bool]:
    raw_slots = premise.get("binds_proposition_slots")
    if not isinstance(raw_slots, list) or any(
        not isinstance(slot, str) for slot in raw_slots
    ):
        return {}
    quote = " ".join(str(premise.get("quote") or "").split())
    if not _is_assertive_proof_span(quote):
        return {slot: False for slot in raw_slots}
    bindings = premise.get("proposition_slot_bindings")
    canonical = proposition_evidence_bindings(proposition)
    if not isinstance(bindings, Mapping) or set(bindings) != set(raw_slots):
        return {slot: False for slot in raw_slots}
    analysis = semantic_relation_clause_analysis(premise, proposition)
    locally_bound = set(analysis.get("slot_evidence") or {})
    return {
        slot: (
            slot in PROPOSITION_EVIDENCE_SLOTS
            and str(bindings.get(slot) or "") == str(canonical.get(slot) or "")
            and not (slot == "quantifier" and str(bindings.get(slot)) == "none")
            and not (slot == "actor" and _is_model_declaration(quote))
            and slot in locally_bound
            and analysis.get("joint_relation_clause_bound") is True
        )
        for slot in raw_slots
    }


def _valid_binding_shape(
    raw_slots: Any,
    raw_bindings: Any,
    canonical_bindings: Mapping[str, str],
) -> bool:
    return bool(
        isinstance(raw_slots, list)
        and raw_slots
        and all(isinstance(slot, str) for slot in raw_slots)
        and len(set(raw_slots)) == len(raw_slots)
        and isinstance(raw_bindings, Mapping)
        and set(raw_bindings) == set(raw_slots)
        and all(
            slot in PROPOSITION_EVIDENCE_SLOTS
            and str(raw_bindings.get(slot) or "")
            == str(canonical_bindings.get(slot) or "")
            for slot in raw_slots
        )
    )


def _audit_slot_evidence_reason(
    premise_index: int,
    raw_slots: list[str],
    quote: str,
    audit_result: Mapping[str, Any] | None,
    *,
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
) -> str:
    if audit_result is None:
        return ""
    checks = audit_result.get("premise_checks") or []
    model_check = (
        checks[premise_index]
        if premise_index < len(checks) and isinstance(checks[premise_index], Mapping)
        else {}
    )
    slot_checks = model_check.get("proposition_slot_checks")
    if not isinstance(slot_checks, list):
        return "semantic_entailment_premise_audit_invalid"
    by_slot = {
        str(slot_check.get("slot")): slot_check
        for slot_check in slot_checks
        if isinstance(slot_check, Mapping)
    }
    if set(by_slot) != set(raw_slots):
        return "semantic_entailment_premise_audit_invalid"
    local_analysis = semantic_relation_clause_analysis(premise, proposition)
    expected_by_slot = dict(local_analysis.get("slot_evidence") or {})
    for slot in raw_slots:
        if by_slot[slot].get("binding_valid") is not True:
            return "semantic_entailment_proposition_binding_unbound"
        expected = expected_by_slot.get(slot)
        evidence_text = str(by_slot[slot].get("evidence_text") or "")
        if (
            not isinstance(expected, Mapping)
            or local_analysis.get("joint_relation_clause_bound") is not True
            or evidence_text != str(expected.get("text") or "")
            or by_slot[slot].get("evidence_ref") != f"P{premise_index + 1}:{slot}"
            or _optional_int(by_slot[slot].get("span_start"))
            != _optional_int(expected.get("span_start"))
            or _optional_int(by_slot[slot].get("span_end"))
            != _optional_int(expected.get("span_end"))
            or by_slot[slot].get("clause_ref") != expected.get("clause_ref")
            or _optional_int(by_slot[slot].get("clause_start"))
            != _optional_int(expected.get("clause_start"))
            or _optional_int(by_slot[slot].get("clause_end"))
            != _optional_int(expected.get("clause_end"))
            or not evidence_text
            or evidence_text not in quote
        ):
            return "semantic_entailment_proposition_binding_unbound"
    return ""


def _is_assertive_proof_span(quote: str) -> bool:
    return bool(
        quote
        and not re.match(r"^#{1,6}\s+", quote)
        and re.search(r'[.!?](?:\]|\)|["\'])?$', quote)
        and re.search(
            r"\b(?:is|are|was|were|be|been|being|has|have|had|"
            r"do|does|did|can|could|may|might|must|shall|should|will|would|"
            r"[a-z]{3,}(?:s|ed|ing))\b",
            quote,
            flags=re.IGNORECASE,
        )
    )


def _is_model_declaration(quote: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:(?:our|the|this|that|a|an|proposed|current|baseline)\s+){0,3}"
            r"(?:model|architecture|classifier|system)\b",
            quote,
            re.IGNORECASE,
        )
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
