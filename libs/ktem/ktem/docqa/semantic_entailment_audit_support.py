from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .boolean_authority_schema import GROUNDED_SEMANTIC_AUDITOR_CONTRACT
from .canonical_serialization import canonical_digest


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def mapping_digest(value: Mapping[str, Any]) -> str:
    return canonical_digest(dict(value))


def validated_auditor(
    audit: Mapping[str, Any],
    *,
    release_mode: bool,
) -> tuple[Mapping[str, Any], str]:
    auditor = audit.get("auditor")
    if not isinstance(auditor, Mapping) or (
        auditor.get("contract_id") != GROUNDED_SEMANTIC_AUDITOR_CONTRACT
        or not str(auditor.get("model") or "").strip()
    ):
        return {}, "semantic_entailment_auditor_attestation_invalid"
    relationship = str(auditor.get("relationship") or "")
    if relationship not in {
        "same_instance",
        "distinct_instance_same_model",
        "distinct_model",
    }:
        return {}, "semantic_entailment_auditor_attestation_invalid"
    if release_mode and relationship != "distinct_model":
        return {}, "release_conclusion_auditor_not_independent"
    return auditor, ""
