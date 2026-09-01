from __future__ import annotations

from typing import Any


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any, *, unique: bool = True) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    values = [str(item).strip() for item in value if str(item).strip()]
    return list(dict.fromkeys(values)) if unique else values


def _same_source(atoms: list[dict[str, Any]]) -> bool:
    source_ids = {str(atom.get("source_id") or "") for atom in atoms}
    return bool(len(source_ids) == 1 and "" not in source_ids)


def _overlapping_premises(atoms: list[dict[str, Any]]) -> bool:
    for index, left in enumerate(atoms):
        for right in atoms[index + 1 :]:
            if str(left.get("evidence_id") or "") != str(
                right.get("evidence_id") or ""
            ):
                continue
            left_start, left_end = left.get("span_start"), left.get("span_end")
            right_start, right_end = right.get("span_start"), right.get("span_end")
            if (
                not isinstance(left_start, int)
                or not isinstance(left_end, int)
                or not isinstance(right_start, int)
                or not isinstance(right_end, int)
            ):
                return True
            if max(left_start, right_start) < min(left_end, right_end):
                return True
    return False
