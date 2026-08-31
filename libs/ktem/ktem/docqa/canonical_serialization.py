"""Shared canonical serialization and digest boundaries for DocQA contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

CANONICAL_SERIALIZER_IDENTITY = "canonical_json_utf8_v1"
CANONICAL_PROJECTION_DIGEST_BOUNDARY = "canonical_projection_digest"


def canonical_json(value: Any) -> str:
    """Serialize a contract value with the one canonical JSON policy."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_projection_payload(value: Any) -> Any:
    """Return projection content without producer-only digest stamps."""

    raw = value.as_dict() if hasattr(value, "as_dict") else value
    if not isinstance(raw, Mapping):
        return raw
    payload = deepcopy(dict(raw))
    premises = payload.get("premises")
    if isinstance(premises, list):
        payload["premises"] = [
            {
                key: item_value
                for key, item_value in premise.items()
                if key != "canonical_projection_digest"
            }
            if isinstance(premise, Mapping)
            else premise
            for premise in premises
        ]
    return payload


def canonical_projection_digest(value: Any) -> str:
    return canonical_digest(canonical_projection_payload(value))


def canonical_digest_trace(
    value: Any,
    *,
    producer_digest: str | None = None,
    boundary: str = CANONICAL_PROJECTION_DIGEST_BOUNDARY,
    projection: bool = False,
) -> dict[str, Any]:
    """Summarize producer/validator digest agreement at one boundary."""

    validator_digest = (
        canonical_projection_digest(value) if projection else canonical_digest(value)
    )
    producer = str(producer_digest or "")
    status = (
        "matched"
        if producer and producer == validator_digest
        else "mismatch"
        if producer
        else "not_observed"
    )
    first_divergence = (
        {
            "boundary": boundary,
            "stage": boundary,
            "reason": f"{boundary}_mismatch",
            "producer_digest": producer,
            "validator_digest": validator_digest,
            "serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
        }
        if status == "mismatch"
        else {}
    )
    return {
        "boundary": boundary,
        "status": status,
        "producer_digest": producer,
        "validator_digest": validator_digest,
        "serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
        "first_divergence": first_divergence,
    }


def canonical_projection_digest_trace(
    value: Any,
    *,
    producer_digest: str | None = None,
) -> dict[str, Any]:
    if producer_digest is None:
        raw = value.as_dict() if hasattr(value, "as_dict") else value
        producer_digest = _projection_producer_digest(raw)
    return canonical_digest_trace(
        value,
        producer_digest=producer_digest,
        boundary=CANONICAL_PROJECTION_DIGEST_BOUNDARY,
        projection=True,
    )


def _projection_producer_digest(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    for premise in value.get("premises") or []:
        if isinstance(premise, Mapping):
            digest = str(premise.get("canonical_projection_digest") or "")
            if digest:
                return digest
    return ""
