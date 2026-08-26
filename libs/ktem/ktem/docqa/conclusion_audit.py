from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .question_proposition import TypedConclusion

CONCLUSION_AUDIT_CONTRACT = "conclusion_audit.v2"
_CONCLUSION_AUDIT_FIELDS = {
    "conclusion_id",
    "conclusion_entailed",
    "actor_consistent",
    "predicate_consistent",
    "object_consistent",
    "polarity_consistent",
    "quantifier_consistent",
    "scope_consistent",
    "auditor_relationship",
    "model",
    "seed",
    "contract_id",
}


@dataclass(frozen=True, slots=True)
class ConclusionAudit:
    """Independent polarity and scope audit of one typed conclusion."""

    conclusion_id: str
    conclusion_entailed: bool
    actor_consistent: bool
    predicate_consistent: bool
    object_consistent: bool
    polarity_consistent: bool
    quantifier_consistent: bool
    scope_consistent: bool
    auditor_relationship: str
    model: str
    seed: int
    contract_id: str = CONCLUSION_AUDIT_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def conclusion_audit_attestation(
    conclusion: TypedConclusion,
    audit_result: Mapping[str, Any],
    *,
    auditor_relationship: str,
    model: str,
    seed: int,
) -> dict[str, Any]:
    return ConclusionAudit(
        conclusion_id=conclusion.conclusion_id,
        conclusion_entailed=audit_result.get("conclusion_entailed") is True,
        actor_consistent=audit_result.get("actor_consistent") is True,
        predicate_consistent=audit_result.get("predicate_consistent") is True,
        object_consistent=audit_result.get("object_consistent") is True,
        polarity_consistent=audit_result.get("polarity_consistent") is True,
        quantifier_consistent=audit_result.get("quantifier_consistent") is True,
        scope_consistent=audit_result.get("scope_consistent") is True,
        auditor_relationship=auditor_relationship,
        model=str(model or ""),
        seed=seed,
    ).as_dict()


def conclusion_audit_digest(audit: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(audit), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def conclusion_audit_validation_reason(
    value: Any,
    conclusion: TypedConclusion,
    *,
    release_mode: bool,
) -> str:
    if not isinstance(value, Mapping):
        return "conclusion_audit_missing"
    if (
        set(value) != _CONCLUSION_AUDIT_FIELDS
        or isinstance(value.get("seed"), bool)
        or not isinstance(value.get("seed"), int)
        or value.get("contract_id") != CONCLUSION_AUDIT_CONTRACT
        or value.get("conclusion_id") != conclusion.conclusion_id
        or not str(value.get("model") or "").strip()
    ):
        return "conclusion_audit_binding_invalid"
    relationship = str(value.get("auditor_relationship") or "")
    if relationship not in {
        "same_instance",
        "distinct_instance_same_model",
        "distinct_model",
    }:
        return "conclusion_auditor_relationship_invalid"
    if release_mode and relationship != "distinct_model":
        return "release_conclusion_auditor_not_independent"
    if any(
        value.get(field) is not True
        for field in (
            "conclusion_entailed",
            "actor_consistent",
            "predicate_consistent",
            "object_consistent",
            "polarity_consistent",
            "quantifier_consistent",
            "scope_consistent",
        )
    ):
        return "conclusion_audit_rejected"
    return ""
