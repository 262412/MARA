from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    QuestionProposition,
    proposition_evidence_bindings,
)
from .semantic_entailment_audit_support import text_digest as _text_digest
from .semantic_relation_clause_validation import semantic_relation_clause_analysis


def semantic_premise_proof_span_reason(
    premises: Sequence[Mapping[str, Any]],
    proposition: QuestionProposition,
    *,
    audit_result: Mapping[str, Any] | None = None,
    canonical_plan_projection: Any | None = None,
) -> str:
    if canonical_plan_projection is not None:
        return _frozen_plan_premise_reason(
            premises,
            audit_result=audit_result,
            canonical_plan_projection=canonical_plan_projection,
        )
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
    canonical_plan_projection: Any | None = None,
) -> str:
    """Validate exact proof spans and model slot evidence before attestation."""

    return semantic_premise_proof_span_reason(
        premises,
        proposition,
        audit_result=audit_result,
        canonical_plan_projection=canonical_plan_projection,
    )


def local_proposition_slot_checks(
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
    *,
    canonical_plan_projection: Any | None = None,
) -> dict[str, bool]:
    if canonical_plan_projection is not None:
        expected = next(
            (
                value
                for value in canonical_plan_projection.premises
                if value.get("evidence_id") == premise.get("evidence_id")
                and value.get("span_selector") == premise.get("span_selector")
            ),
            None,
        )
        if expected is None:
            return {}
        expected_slots = list(expected.get("binds_proposition_slots") or [])
        if list(premise.get("binds_proposition_slots") or []) != expected_slots or dict(
            premise.get("proposition_slot_bindings") or {}
        ) != dict(expected.get("proposition_slot_bindings") or {}):
            return {slot: False for slot in expected_slots}
        return {slot: True for slot in expected_slots}
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
    canonical_plan_projection: Any | None = None,
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
    if canonical_plan_projection is not None:
        expected_by_slot = canonical_plan_projection.audit_slot_evidence.get(
            f"P{premise_index + 1}", {}
        )
        local_bound = True
    else:
        local_analysis = semantic_relation_clause_analysis(premise, proposition)
        expected_by_slot = dict(local_analysis.get("slot_evidence") or {})
        local_bound = local_analysis.get("joint_relation_clause_bound") is True
    for slot in raw_slots:
        if by_slot[slot].get("binding_valid") is not True:
            return "semantic_entailment_proposition_binding_unbound"
        expected = expected_by_slot.get(slot)
        evidence_text = str(by_slot[slot].get("evidence_text") or "")
        if (
            not isinstance(expected, Mapping)
            or not local_bound
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


def _frozen_plan_premise_reason(
    premises: Sequence[Mapping[str, Any]],
    *,
    audit_result: Mapping[str, Any] | None,
    canonical_plan_projection: Any,
) -> str:
    expected = canonical_plan_projection.premises
    if len(premises) != len(expected):
        return "semantic_entailment_premise_count_invalid"
    checks: list[Any] | None = None
    if audit_result is not None:
        raw_checks = audit_result.get("premise_checks")
        if not isinstance(raw_checks, list) or len(raw_checks) != len(expected):
            return "semantic_entailment_premise_audit_invalid"
        checks = raw_checks
    for index, (premise, frozen) in enumerate(zip(premises, expected), start=1):
        if (
            not isinstance(premise, Mapping)
            or premise.get("evidence_id") != frozen.get("evidence_id")
            or premise.get("span_selector") != frozen.get("span_selector")
            or premise.get("quote") != frozen.get("quote")
            or premise.get("span_start") != frozen.get("span_start")
            or premise.get("span_end") != frozen.get("span_end")
            or premise.get("canonical_start") != frozen.get("canonical_start")
            or premise.get("canonical_end") != frozen.get("canonical_end")
            or list(premise.get("binds_proposition_slots") or [])
            != list(frozen.get("binds_proposition_slots") or [])
            or dict(premise.get("proposition_slot_bindings") or {})
            != dict(frozen.get("proposition_slot_bindings") or {})
            or premise.get("evidence_relation") != frozen.get("evidence_relation")
            or premise.get("canonical_evidence_plan_id")
            != frozen.get("canonical_evidence_plan_id")
            or premise.get("canonical_plan_digest")
            != frozen.get("canonical_plan_digest")
        ):
            return "semantic_entailment_proposition_binding_unbound"
        if checks is not None:
            check = checks[index - 1]
            if not isinstance(check, Mapping) or not _frozen_audit_check_valid(
                check,
                index=index,
                premise=frozen,
                expected_slots=canonical_plan_projection.audit_slot_evidence[
                    f"P{index}"
                ],
            ):
                return "semantic_entailment_proposition_binding_unbound"
    return ""


def _frozen_audit_check_valid(
    check: Mapping[str, Any],
    *,
    index: int,
    premise: Mapping[str, Any],
    expected_slots: Mapping[str, Mapping[str, Any]],
) -> bool:
    if not all(
        check.get(field) is True
        for field in (
            "fragment_entailed",
            "scope_consistent",
            "evidence_relation_valid",
        )
    ):
        return False
    expected_declared_slots = list(premise.get("binds_proposition_slots") or [])
    if check.get("declared_proposition_slots") != expected_declared_slots:
        return False
    if "premise_ref" in check:
        if (
            check.get("premise_ref") != f"P{index}"
            or check.get("proposition_bindings_valid") is not True
        ):
            return False
    elif (
        check.get("premise_index") != index
        or check.get("evidence_id") != premise.get("evidence_id")
        or check.get("quote_digest") != _text_digest(str(premise.get("quote") or ""))
        or check.get("fragment_digest")
        != _text_digest(str(premise.get("proposition_fragment") or ""))
        or check.get("proposition_bindings_valid") is not True
        or check.get("evidence_relation") != premise.get("evidence_relation")
    ):
        return False
    slot_checks = check.get("proposition_slot_checks")
    if not isinstance(slot_checks, list) or len(slot_checks) != len(expected_slots):
        return False
    for slot_check in slot_checks:
        if not isinstance(slot_check, Mapping):
            return False
        slot = str(slot_check.get("slot") or "")
        expected = expected_slots.get(slot)
        if (
            not isinstance(expected, Mapping)
            or slot_check.get("binding_valid") is not True
            or slot_check.get("evidence_ref") != f"P{index}:{slot}"
            or slot_check.get("evidence_text") != expected.get("text")
            or _optional_int(slot_check.get("span_start"))
            != _optional_int(expected.get("span_start"))
            or _optional_int(slot_check.get("span_end"))
            != _optional_int(expected.get("span_end"))
            or slot_check.get("clause_ref") != expected.get("clause_ref")
            or _optional_int(slot_check.get("clause_start"))
            != _optional_int(expected.get("clause_start"))
            or _optional_int(slot_check.get("clause_end"))
            != _optional_int(expected.get("clause_end"))
        ):
            return False
    return True
