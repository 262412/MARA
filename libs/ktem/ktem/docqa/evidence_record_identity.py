from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of


def unique_evidence_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        try:
            identity = identity_of(record).key
        except ValueError:
            continue
        if identity in seen:
            continue
        seen.add(identity)
        output.append(record)
    return output
