from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import QuestionProposition, typed_conclusion
from ktem.docqa.semantic_entailment_audit import (
    semantic_entailment_audit_validation_reason,
)


def conclusion_audit_binding_reason(
    question: str,
    value: dict[str, Any],
    proposition: QuestionProposition,
    *,
    release_mode: bool,
) -> str:
    return semantic_entailment_audit_validation_reason(
        question,
        str(value["verdict"]),
        value["premises"],
        value["entailment_audit"],
        proof_mode=str(value.get("proof_mode") or ""),
        proposition=proposition,
        conclusion=typed_conclusion(proposition, str(value["verdict"])),
        release_mode=release_mode,
    )


def record_verified_conclusion_audit(
    diagnostics: dict[str, Any], value: dict[str, Any]
) -> None:
    diagnostics.update(
        {
            "audit_status": "verified",
            "audit_reason": "",
            "audit_proposal_digest": value["entailment_audit"]["proposal_digest"],
            "proof_mode": str(value.get("proof_mode") or ""),
            "typed_conclusion": dict(value.get("typed_conclusion") or {}),
            "conclusion_audit": dict(
                value["entailment_audit"].get("conclusion_audit") or {}
            ),
        }
    )
