from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.question_proposition import (
    QuestionProposition,
    QuestionPropositionResolution,
    build_question_proposition,
    resolve_question_proposition,
)


@dataclass(frozen=True)
class SemanticPropositionTransactionResult:
    value: dict[str, Any] | None
    status: str
    reason: str
    diagnostics: dict[str, Any]
    proposal_call_count: int
    audit_call_count: int
    debug_trace: dict[str, Any] | None = None


@dataclass(frozen=True)
class SemanticPropositionTransactionContext:
    proposal_llm: Any
    audit_llm: Any
    proposal_prompt: str
    question: str
    packed: list[dict[str, Any]]
    slots: list[dict[str, str]]
    proposition: QuestionProposition
    proposition_resolution: dict[str, Any]
    proposal_model: str
    audit_model: str
    seed: int
    release_mode: bool
    semantic_pack_digest: str
    capture_debug_trace: bool
    auditor_relationship: str
    transaction_id: str = ""
    attempt_namespace: str = "initial"
    canonical_span_universe_digest: str = ""
    candidate_transaction_id: str = ""


def resolve_proposition_precondition(
    question: str,
    diagnostics: dict[str, Any],
) -> QuestionPropositionResolution:
    """Resolve and record the typed proposition before any model audit."""

    resolution = resolve_question_proposition(question)
    diagnostics.update(
        {
            "question_proposition_status": resolution.status,
            "question_proposition_reason": resolution.reason,
            "question_proposition_resolution": resolution.as_dict(),
            "proposition_repair_count": int(resolution.status == "repaired"),
        }
    )
    if resolution.status != "complete":
        diagnostics.setdefault("recovery_transitions", []).append(
            {
                "from": "question_proposition",
                "to": "proposition_repair",
                "reason": resolution.reason,
                "outcome": resolution.status,
            }
        )
    return resolution


def insufficient_semantic_result(
    model: str,
    seed: int,
    question: str = "",
) -> dict[str, Any]:
    result = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "insufficient_evidence",
        "evidence_relation": "undetermined",
        "support_mode": "evidence_set",
        "proof_mode": "none",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }
    if question:
        result["question_proposition"] = build_question_proposition(question).as_dict()
    return result


def incomplete_proposition_result(
    resolution: QuestionPropositionResolution,
    diagnostics: dict[str, Any],
    *,
    proposal_model: str,
    seed: int,
    question: str,
    release_mode: bool,
    relationship: str,
    semantic_pack_digest: str,
) -> SemanticPropositionTransactionResult:
    value = insufficient_semantic_result(proposal_model, seed, question)
    value["question_proposition_resolution"] = resolution.as_dict()
    value["verifier"].update(
        {
            "release_mode": release_mode,
            "auditor_relationship": relationship,
            "semantic_pack_digest": semantic_pack_digest,
        }
    )
    return SemanticPropositionTransactionResult(
        value=value,
        status="proposition_incomplete",
        reason=resolution.reason,
        diagnostics=diagnostics,
        proposal_call_count=0,
        audit_call_count=0,
    )


def rejected_semantic_transaction(
    value: dict[str, Any],
    *,
    reason: str,
    semantic_pack_digest: str,
    raw_audit_result: dict[str, Any] | None = None,
    local_premise_consistency: dict[str, Any] | None = None,
    independent_semantic_constraint: dict[str, Any] | None = None,
    semantic_proof_digest: str = "",
    semantic_pack_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    audit = value.get("entailment_audit")
    audit = audit if isinstance(audit, dict) else {}
    transaction = {
        "runtime_rejection_reason": reason,
        "proof_mode": str(value.get("proof_mode") or ""),
        "typed_conclusion": dict(value.get("typed_conclusion") or {}),
        "conclusion_audit": dict(audit.get("conclusion_audit") or {}),
        "polarity_contradiction_check": dict(
            audit.get("polarity_contradiction_check") or {}
        ),
        "semantic_pack_digest": semantic_pack_digest,
        "premises": list(value.get("premises") or []),
    }
    if raw_audit_result is not None:
        transaction["raw_conclusion_check"] = dict(
            raw_audit_result.get("conclusion_check") or {}
        )
    if local_premise_consistency is not None:
        transaction["local_premise_consistency"] = dict(local_premise_consistency)
    if independent_semantic_constraint is not None:
        transaction["independent_semantic_constraint"] = dict(
            independent_semantic_constraint
        )
    if semantic_proof_digest:
        transaction["semantic_proof_digest"] = semantic_proof_digest
    if semantic_pack_identity is not None:
        transaction["semantic_pack_identity"] = dict(semantic_pack_identity)
    return transaction
