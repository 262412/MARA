from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .evidence_fact_contract import (
    STRUCTURED_FACT_FIELDS,
    EvidenceIdentityConflictError,
)
from .evidence_field_values import score_value
from .evidence_identity import canonicalize_and_dedupe_evidence, identity_of


@dataclass(frozen=True)
class EvidenceRecordIngestionResult:
    accepted_records: tuple[dict[str, Any], ...]
    identity_conflicts: tuple[dict[str, Any], ...]

    @property
    def status(self) -> str:
        return "partial" if self.identity_conflicts else "complete"

    @property
    def accepted_record_count(self) -> int:
        return len(self.accepted_records)

    @property
    def rejected_record_count(self) -> int:
        return len(self.identity_conflicts)

    @property
    def identity_conflict_count(self) -> int:
        return len(self.identity_conflicts)

    def as_trace(self) -> dict[str, Any]:
        return {
            "element_ingestion_status": self.status,
            "accepted_record_count": self.accepted_record_count,
            "rejected_record_count": self.rejected_record_count,
            "identity_conflict_count": self.identity_conflict_count,
            "identity_conflicts": [dict(item) for item in self.identity_conflicts],
        }


def unique_evidence_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return list(isolate_evidence_records(records).accepted_records)


def isolate_evidence_records(
    records: Iterable[dict[str, Any]],
) -> EvidenceRecordIngestionResult:
    output: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    for record in records:
        try:
            identity = identity_of(record).key
        except ValueError:
            continue
        position = positions.get(identity)
        if position is None:
            positions[identity] = len(output)
            output.append(record)
            continue
        existing = output[position]
        try:
            merged, _trace = canonicalize_and_dedupe_evidence([existing, record])
        except EvidenceIdentityConflictError as exc:
            conflicts.append(
                _identity_conflict(
                    identity,
                    existing=existing,
                    incoming=record,
                    error=exc,
                )
            )
            continue
        if len(merged) != 1:
            continue
        _merge_provenance(output[position], record, merged[0])
    return EvidenceRecordIngestionResult(
        accepted_records=tuple(output),
        identity_conflicts=tuple(conflicts),
    )


def _identity_conflict(
    identity: str,
    *,
    existing: dict[str, Any],
    incoming: dict[str, Any],
    error: EvidenceIdentityConflictError,
) -> dict[str, Any]:
    fields = [
        field
        for field in STRUCTURED_FACT_FIELDS
        if existing.get(field) not in (None, "")
        and incoming.get(field) not in (None, "")
        and str(existing[field]) != str(incoming[field])
    ]
    if not fields:
        fields = ["textual_facts"]
    return {
        "derived_identity": identity,
        "conflicting_fields": fields,
        "existing_record": _record_locator(existing),
        "incoming_record": _record_locator(incoming),
        "error": str(error),
    }


def _record_locator(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "evidence_id",
            "source_id",
            "page_label",
            "element_id",
            "table_id",
            "cell_id",
            "span_id",
            "row_index",
            "column_index",
            "period",
            "value",
        )
        if record.get(key) not in (None, "")
    }


def _merge_provenance(
    target: dict[str, Any],
    duplicate: dict[str, Any],
    canonical: dict[str, Any],
) -> None:
    for key in (
        "source_backrefs",
        "retrieval_lineage",
        "representations",
        "duplicate_evidence_ids",
    ):
        if canonical.get(key):
            target[key] = list(canonical[key])
    target_metadata = dict(target.get("metadata") or {})
    target_metadata.update(dict(canonical.get("metadata") or {}))
    target["metadata"] = target_metadata
    for key, value in duplicate.items():
        if key == "scores" and isinstance(value, dict):
            scores = dict(target.get("scores") or {})
            scores.update(value)
            target["scores"] = scores
            continue
        if key == "score" or key.endswith("_score"):
            target[key] = max(score_value(target.get(key)), score_value(value))
            continue
        if target.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            target[key] = value
