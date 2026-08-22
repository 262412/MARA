from __future__ import annotations

from typing import Any

QASPER_AUTHORITY_DIAGNOSTIC_FIELDS = (
    "qasper_composite_authority_count",
    "qasper_composite_authority_invalid_count",
    "qasper_semantic_evidence_set_authority_count",
    "qasper_semantic_evidence_set_authority_invalid_count",
    "qasper_semantic_proposition_verifier_call_count",
    "qasper_semantic_proposition_verifier_failure_count",
    "qasper_semantic_proposition_verifier_context_overflow_count",
    "qasper_semantic_proposition_verifier_schema_unsupported_count",
    "qasper_required_slot_authority_empty_count",
    "qasper_required_slot_authority_missing_count",
)


def qasper_authority_diagnostics_markdown(summary: dict[str, Any]) -> list[str]:
    values = [
        (field, summary[field])
        for field in QASPER_AUTHORITY_DIAGNOSTIC_FIELDS
        if field in summary
    ]
    if not values:
        return []
    lines = [
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {field} | {value} |" for field, value in values)
    return lines
