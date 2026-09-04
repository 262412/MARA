from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from .mara_qasper_candidate_identity import candidate_digest


def qasper_selector_crosswalk(
    source_records: Sequence[Mapping[str, Any]],
    canonical_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Map selector identities across windowing and candidate re-enumeration."""

    source = _source_selector_records(source_records)
    canonical = _canonical_selector_records(canonical_records)
    canonical_rows = [
        _canonical_crosswalk_row(row, source, source_records, canonical_records)
        for row in canonical
    ]
    source_rows = [
        {
            **row,
            "canonical_selector_refs": [
                candidate["selector_ref"]
                for candidate in canonical
                if _same_span_identity(row, candidate)
            ],
            "decision": (
                "preserved_in_canonical_universe"
                if any(_same_span_identity(row, candidate) for candidate in canonical)
                else "not_in_canonical_selector_universe"
            ),
        }
        for row in source
    ]
    mapped_count = sum(row["mapped"] for row in canonical_rows)
    complete = bool(canonical_rows) and mapped_count == len(canonical_rows)
    payload = {
        "contract_id": "qasper_selector_crosswalk.v1",
        "complete": complete,
        "source_selector_count": len(source_rows),
        "canonical_selector_count": len(canonical_rows),
        "mapped_canonical_selector_count": mapped_count,
        "source_selectors": source_rows,
        "canonical_selectors": canonical_rows,
    }
    payload["crosswalk_digest"] = candidate_digest(payload)
    return payload


def _source_selector_records(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        evidence_id = str(record.get("evidence_id") or "")
        for selector in record.get("selectors") or []:
            if not isinstance(selector, Mapping):
                continue
            output.append(
                _selector_identity(
                    selector,
                    evidence_id=evidence_id,
                    ref_key="source_selector_ref",
                )
            )
    return output


def _canonical_selector_records(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        evidence_id = str(record.get("evidence_id") or "")
        for selector in record.get("selectors") or []:
            if not isinstance(selector, Mapping):
                continue
            output.append(
                _selector_identity(
                    selector,
                    evidence_id=evidence_id,
                    ref_key="selector_ref",
                )
            )
    return output


def _selector_identity(
    selector: Mapping[str, Any],
    *,
    evidence_id: str,
    ref_key: str,
) -> dict[str, Any]:
    text = str(selector.get("text") or "")
    identity = {
        "evidence_id": evidence_id,
        "span_start": selector.get("span_start"),
        "span_end": selector.get("span_end"),
        "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return {
        ref_key: str(selector.get("selector_id") or ""),
        **identity,
        "span_identity_digest": candidate_digest(identity),
    }


def _canonical_crosswalk_row(
    canonical: dict[str, Any],
    source: list[dict[str, Any]],
    source_records: Sequence[Mapping[str, Any]],
    canonical_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    exact_refs = [
        row["source_selector_ref"]
        for row in source
        if _same_span_identity(row, canonical)
    ]
    source_record_found = any(
        str(record.get("evidence_id") or "") == canonical["evidence_id"]
        for record in source_records
    )
    candidate_projection_recorded = _candidate_projection_selected(
        canonical,
        canonical_records,
    )
    inside_window = _inside_source_window(canonical, source_records)
    origin = (
        "source_window_selector"
        if exact_refs
        else "candidate_source_reenumeration"
        if source_record_found and candidate_projection_recorded
        else "canonical_projection_unattributed"
        if source_record_found
        else "source_record_missing"
    )
    return {
        "canonical_selector_ref": canonical["selector_ref"],
        "evidence_id": canonical["evidence_id"],
        "span_start": canonical["span_start"],
        "span_end": canonical["span_end"],
        "text_digest": canonical["text_digest"],
        "span_identity_digest": canonical["span_identity_digest"],
        "source_selector_refs": exact_refs,
        "source_window_status": (
            "inside_packed_window" if inside_window else "outside_packed_window"
        ),
        "candidate_projection_recorded": candidate_projection_recorded,
        "origin": origin,
        "mapped": origin
        in {"source_window_selector", "candidate_source_reenumeration"},
    }


def _same_span_identity(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return all(
        first.get(field) == second.get(field)
        for field in ("evidence_id", "span_start", "span_end", "text_digest")
    )


def _candidate_projection_selected(
    canonical: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> bool:
    for record in records:
        if str(record.get("evidence_id") or "") != canonical.get("evidence_id"):
            continue
        trace = record.get("candidate_selector_projection_trace")
        if not isinstance(trace, Mapping) or trace.get("complete") is not True:
            continue
        decisions = trace.get("decisions")
        if not isinstance(decisions, list):
            continue
        if any(
            isinstance(decision, Mapping)
            and decision.get("selected") is True
            and decision.get("span_start") == canonical.get("span_start")
            and decision.get("span_end") == canonical.get("span_end")
            and decision.get("text_digest") == canonical.get("text_digest")
            for decision in decisions
        ):
            return True
    return False


def _inside_source_window(
    canonical: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> bool:
    start = canonical.get("span_start")
    end = canonical.get("span_end")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    for record in records:
        if str(record.get("evidence_id") or "") != canonical.get("evidence_id"):
            continue
        window_start = record.get("text_start")
        if not isinstance(window_start, int):
            continue
        window_end = window_start + len(str(record.get("text") or ""))
        if window_start <= start < end <= window_end:
            return True
    return False
