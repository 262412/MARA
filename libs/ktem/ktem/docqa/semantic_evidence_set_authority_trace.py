from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def canonical_projection_trace(
    response: Mapping[str, Any],
    *,
    attestation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    for value in (
        attestation,
        _mapping(response.get("canonical_projection_digest_trace")),
        _mapping(response.get("entailment_audit")),
    ):
        if not isinstance(value, Mapping):
            continue
        trace = value.get("canonical_projection_digest_trace")
        if isinstance(trace, Mapping):
            return dict(trace)
        constraint = value.get("independent_semantic_constraint")
        if isinstance(constraint, Mapping):
            trace = constraint.get("canonical_projection_digest_trace")
            if isinstance(trace, Mapping):
                return dict(trace)
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
