from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .semantic_entailment_audit_support import as_int as _as_int
from .semantic_entailment_audit_support import mapping_digest as _mapping_digest
from .semantic_entailment_audit_support import text_digest as _text_digest


def premise_audit_validation_reason(
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
        if not _premise_check_identity_valid(check, premise, premise_index=index):
            return "semantic_entailment_premise_audit_invalid"
        analysis = analyses[index - 1] if index <= len(analyses) else {}
        if not _premise_slot_checks_valid(
            check,
            premise,
            analysis=analysis,
            premise_index=index,
        ):
            return "semantic_entailment_premise_audit_invalid"
    return ""


def _premise_check_identity_valid(
    check: Any,
    premise: Mapping[str, Any],
    *,
    premise_index: int,
) -> bool:
    if not isinstance(check, Mapping):
        return False
    bindings = {
        str(slot): str(binding)
        for slot, binding in dict(
            premise.get("proposition_slot_bindings") or {}
        ).items()
    }
    return bool(
        _as_int(check.get("premise_index")) == premise_index
        and check.get("evidence_id") == str(premise.get("evidence_id") or "")
        and check.get("quote_digest") == _text_digest(str(premise.get("quote") or ""))
        and check.get("fragment_digest")
        == _text_digest(str(premise.get("proposition_fragment") or ""))
        and check.get("fragment_entailed") is True
        and check.get("scope_consistent") is True
        and check.get("proposition_bindings_valid") is True
        and check.get("evidence_relation_valid") is True
        and check.get("proposition_binding_digest") == _mapping_digest(bindings)
        and check.get("evidence_relation")
        == str(premise.get("evidence_relation") or "")
    )


def _premise_slot_checks_valid(
    check: Mapping[str, Any],
    premise: Mapping[str, Any],
    *,
    analysis: Any,
    premise_index: int,
) -> bool:
    declared_slots = [
        str(slot) for slot in premise.get("binds_proposition_slots") or []
    ]
    raw_slot_checks = check.get("proposition_slot_checks")
    expected_slot_evidence = (
        dict(analysis.get("slot_evidence") or {})
        if isinstance(analysis, Mapping)
        else {}
    )
    return bool(
        check.get("declared_proposition_slots") == declared_slots
        and isinstance(raw_slot_checks, list)
        and [
            str(slot_check.get("slot"))
            for slot_check in raw_slot_checks
            if isinstance(slot_check, Mapping)
        ]
        == declared_slots
        and all(
            _slot_check_valid(
                slot_check,
                expected_slot_evidence,
                premise_index=premise_index,
            )
            for slot_check in raw_slot_checks
        )
    )


def _slot_check_valid(
    slot_check: Any,
    expected_slot_evidence: Mapping[str, Any],
    *,
    premise_index: int,
) -> bool:
    expected_fields = {
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
    return bool(
        isinstance(slot_check, Mapping)
        and set(slot_check) == expected_fields
        and slot_check.get("binding_valid") is True
        and _slot_check_matches_local_span(
            slot_check,
            expected_slot_evidence.get(str(slot_check.get("slot") or "")),
            premise_index=premise_index,
        )
    )


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


def verified_audit_result(
    audit_result: Mapping[str, Any],
    premise_count: int,
) -> dict[str, Any]:
    value = dict(audit_result)
    checks = value.get("premise_checks")
    conclusion = value.get("conclusion_check")
    if (
        not isinstance(checks, list)
        or len(checks) != premise_count
        or any(not _verified_premise_check(check) for check in checks)
        or value.get("jointly_entails") is not True
        or value.get("each_premise_required") is not True
        or value.get("contradiction_free") is not True
        or not _verified_conclusion_check(conclusion)
    ):
        raise ValueError(
            "A verified attestation requires a fully passing audit result."
        )
    return value


def _verified_premise_check(check: Any) -> bool:
    return bool(
        isinstance(check, Mapping)
        and check.get("fragment_entailed") is True
        and check.get("scope_consistent") is True
        and check.get("proposition_bindings_valid") is True
        and check.get("evidence_relation_valid") is True
        and isinstance(check.get("declared_proposition_slots"), list)
        and bool(check.get("declared_proposition_slots"))
        and isinstance(check.get("proposition_slot_checks"), list)
        and len(check.get("proposition_slot_checks") or [])
        == len(check.get("declared_proposition_slots") or [])
        and all(
            isinstance(slot_check, Mapping)
            and slot_check.get("binding_valid") is True
            and bool(str(slot_check.get("evidence_text") or "").strip())
            for slot_check in check.get("proposition_slot_checks") or []
        )
    )


def _verified_conclusion_check(conclusion: Any) -> bool:
    required = (
        "conclusion_entailed",
        "actor_consistent",
        "predicate_consistent",
        "object_consistent",
        "polarity_consistent",
        "quantifier_consistent",
        "scope_consistent",
    )
    return bool(
        isinstance(conclusion, Mapping)
        and all(conclusion.get(field) is True for field in required)
    )
