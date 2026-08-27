from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS

PRE_AUDIT_SLOT_EVIDENCE_MISMATCH = "pre_audit_slot_evidence_mismatch"
PRE_AUDIT_SCHEMA_VALIDATION_FAILED = "pre_audit_schema_validation_failed"

_EXACT_SPAN_EVIDENCE_FIELDS = frozenset(
    {
        "text",
        "span_start",
        "span_end",
        "clause_ref",
        "clause_start",
        "clause_end",
        "evidence_ref",
    }
)


def audit_preflight_failure_reason(
    premise_labels: Collection[str],
    *,
    premise_slot_expectations: Mapping[str, Collection[str]] | None,
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None,
) -> str:
    """Validate the audit's local per-premise slot contract before schema build."""

    if premise_slot_expectations is None:
        return ""
    labels = tuple(str(label) for label in premise_labels)
    if premise_slot_evidence is None:
        return PRE_AUDIT_SLOT_EVIDENCE_MISMATCH
    if set(premise_slot_expectations) != set(labels) or set(
        premise_slot_evidence
    ) != set(labels):
        return PRE_AUDIT_SLOT_EVIDENCE_MISMATCH
    allowed_slots = set(PROPOSITION_EVIDENCE_SLOTS)
    for label in labels:
        expected = tuple(str(slot) for slot in premise_slot_expectations.get(label, ()))
        evidence = premise_slot_evidence.get(label)
        if (
            not expected
            or len(set(expected)) != len(expected)
            or not set(expected) <= allowed_slots
            or not isinstance(evidence, Mapping)
            or set(evidence) != set(expected)
            or any(
                not _exact_span_evidence_valid(label, slot, evidence.get(slot))
                for slot in expected
            )
        ):
            return PRE_AUDIT_SLOT_EVIDENCE_MISMATCH
    return ""


def _exact_span_evidence_valid(label: str, slot: str, value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _EXACT_SPAN_EVIDENCE_FIELDS:
        return False
    if value.get("evidence_ref") != f"{label}:{slot}":
        return False
    if (
        not isinstance(value.get("text"), str)
        or not value["text"].strip()
        or not isinstance(value.get("clause_ref"), str)
        or not value["clause_ref"].strip()
    ):
        return False
    offsets = tuple(
        value[field]
        for field in ("span_start", "span_end", "clause_start", "clause_end")
    )
    if any(
        not isinstance(offset, int) or isinstance(offset, bool) for offset in offsets
    ):
        return False
    span_start, span_end, clause_start, clause_end = offsets
    return (
        span_start >= clause_start and span_end > span_start and span_end <= clause_end
    )
