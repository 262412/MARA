from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import typed_conclusion
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation

from .mara_semantic_transaction_support import semantic_pack_identity


def attach_verified_entailment_audit(
    value: dict[str, Any],
    context: Any,
    audit_result: dict[str, Any],
    local_constraint: dict[str, Any],
) -> None:
    value["entailment_audit"] = semantic_entailment_audit_attestation(
        context.question,
        value["verdict"],
        value["premises"],
        model=context.audit_model,
        seed=context.seed + 1,
        proof_mode=str(value.get("proof_mode") or ""),
        proposition=context.proposition,
        conclusion=typed_conclusion(context.proposition, str(value["verdict"])),
        auditor_relationship=context.auditor_relationship,
        audit_result=audit_result,
        independent_semantic_constraint=local_constraint,
    )
    value["entailment_audit"]["semantic_pack_identity"] = semantic_pack_identity(
        context
    )
