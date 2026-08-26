from __future__ import annotations

import re
from typing import Any

_PARENT_SPAN_REF = re.compile(r"^(?P<evidence>.+)#quote:(?P<start>\d+):(?P<end>\d+)$")
_SLOT_SPAN_REF = re.compile(
    r"^(?P<parent>.+)#slot:(?P<slot>actor|predicate|object|quantifier):"
    r"(?P<start>\d+):(?P<end>\d+)$"
)


def _parsed_parent_span_refs(value: Any) -> list[tuple[str, int, int]] | None:
    if not isinstance(value, list) or not value:
        return None
    parsed = [_parse_parent_span_ref(item) for item in value]
    if any(item is None for item in parsed):
        return None
    result = [item for item in parsed if item is not None]
    identities = {_parent_span_identity(item) for item in result}
    return result if len(identities) == len(result) else None


def _parse_parent_span_ref(value: Any) -> tuple[str, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _PARENT_SPAN_REF.fullmatch(value)
    if match is None:
        return None
    evidence_id = match.group("evidence")
    start = int(match.group("start"))
    end = int(match.group("end"))
    if not evidence_id or end <= start:
        return None
    if value != _canonical_parent_span_ref((evidence_id, start, end)):
        return None
    return evidence_id, start, end


def _parse_slot_span_ref(value: Any) -> tuple[str, str, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _SLOT_SPAN_REF.fullmatch(value)
    if match is None:
        return None
    parent_ref = match.group("parent")
    slot = match.group("slot")
    start = int(match.group("start"))
    end = int(match.group("end"))
    parent = _parse_parent_span_ref(parent_ref)
    if parent is None or end <= start:
        return None
    if value != _canonical_slot_span_ref(parent, slot, start, end):
        return None
    return parent_ref, slot, start, end


def _canonical_parent_span_ref(parsed: tuple[str, int, int]) -> str:
    evidence_id, start, end = parsed
    return f"{evidence_id}#quote:{start}:{end}"


def _canonical_slot_span_ref(
    parent: tuple[str, int, int],
    slot: str,
    start: int,
    end: int,
) -> str:
    return f"{_canonical_parent_span_ref(parent)}#slot:{slot}:{start}:{end}"


def _parent_span_identity(parsed: tuple[str, int, int]) -> tuple[str, int, int]:
    return parsed


def _child_span_identity(
    parent: tuple[str, int, int],
    slot: str,
    start: int,
    end: int,
) -> tuple[Any, ...]:
    return (*_parent_span_identity(parent), slot, start, end)


def _child_span_contained(
    parent: tuple[str, int, int],
    start: int,
    end: int,
) -> bool:
    return parent[1] <= start < end <= parent[2]


def _projected_slot_evidence_children(
    value: Any,
    *,
    required_proposition_slots: set[str],
    parent_identities: set[tuple[str, int, int]],
) -> dict[str, dict[tuple[Any, ...], str]] | None:
    if not isinstance(value, dict) or not value:
        return None
    by_slot: dict[str, dict[tuple[Any, ...], str]] = {
        slot: {} for slot in required_proposition_slots
    }
    observed_parents: set[tuple[str, int, int]] = set()
    for parent_ref, slot_values in value.items():
        parent = _parse_parent_span_ref(parent_ref)
        if (
            parent is None
            or _parent_span_identity(parent) not in parent_identities
            or not isinstance(slot_values, dict)
            or not slot_values
            or set(slot_values) - required_proposition_slots
        ):
            return None
        observed_parents.add(_parent_span_identity(parent))
        for slot, evidence in slot_values.items():
            if not _slot_evidence_record_valid(
                evidence,
                parent=parent,
                slot=slot,
            ):
                return None
            assert isinstance(evidence, dict)
            parsed = _parse_slot_span_ref(evidence.get("evidence_ref"))
            assert parsed is not None
            _parent_ref, parsed_slot, start, end = parsed
            identity = _child_span_identity(parent, parsed_slot, start, end)
            canonical_ref = _canonical_slot_span_ref(parent, parsed_slot, start, end)
            if identity in by_slot[slot]:
                return None
            by_slot[slot][identity] = canonical_ref
    if observed_parents != parent_identities:
        return None
    return by_slot


def _slot_evidence_record_valid(
    value: Any,
    *,
    parent: tuple[str, int, int],
    slot: str,
) -> bool:
    if not isinstance(value, dict):
        return False
    parsed = _parse_slot_span_ref(value.get("evidence_ref"))
    if parsed is None:
        return False
    parent_ref, parsed_slot, start, end = parsed
    if (
        parsed_slot != slot
        or parent_ref != _canonical_parent_span_ref(parent)
        or not _child_span_contained(parent, start, end)
        or not isinstance(value.get("text"), str)
        or not value["text"].strip()
        or len(value["text"]) != end - start
        or not isinstance(value.get("clause_ref"), str)
        or not value["clause_ref"].strip()
        or not _valid_span_offsets(value, start, end, parent)
    ):
        return False
    return True


def _valid_span_offsets(
    value: dict[str, Any],
    start: int,
    end: int,
    parent: tuple[str, int, int],
) -> bool:
    span_start = value.get("span_start")
    span_end = value.get("span_end")
    clause_start = value.get("clause_start")
    clause_end = value.get("clause_end")
    if any(
        not isinstance(item, int) or isinstance(item, bool)
        for item in (
            span_start,
            span_end,
            clause_start,
            clause_end,
        )
    ):
        return False
    assert isinstance(span_start, int)
    assert isinstance(span_end, int)
    assert isinstance(clause_start, int)
    assert isinstance(clause_end, int)
    return (
        span_start == start
        and span_end == end
        and parent[1] <= clause_start < clause_end <= parent[2]
        and clause_start <= start < end <= clause_end
    )
