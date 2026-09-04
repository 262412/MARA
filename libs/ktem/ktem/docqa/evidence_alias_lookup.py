from __future__ import annotations

from typing import Any

from .evidence_identity import exact_evidence_aliases, identity_of


def unambiguous_evidence_alias_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, dict[str, Any]]] = {}
    for item in items:
        try:
            identity_key = identity_of(item).key
        except ValueError:
            # Diagnostic-only legacy evidence can have no durable locator.
            continue
        for alias in exact_evidence_aliases(item):
            candidates.setdefault(alias, {})[identity_key] = item
    return {
        alias: next(iter(by_identity.values()))
        for alias, by_identity in candidates.items()
        if len(by_identity) == 1
    }
