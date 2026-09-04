from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ktem_contracts import terminal_semantic_commit as _terminal_contract

from .boolean_claim_verification import canonical_boolean_answer_polarity
from .evidence import EvidenceBundle
from .execution_contracts import ABSTAIN_MESSAGE
from .execution_models import GuardrailDecision
from .verification import VerifyDecision

LEGACY_TERMINAL_SEMANTIC_COMMIT_CONTRACT = (
    _terminal_contract.LEGACY_TERMINAL_SEMANTIC_COMMIT_CONTRACT
)
OPERATIONAL_TERMINAL_OUTCOMES = _terminal_contract.OPERATIONAL_TERMINAL_OUTCOMES
TERMINAL_OUTCOMES = _terminal_contract.TERMINAL_OUTCOMES
TERMINAL_SEMANTIC_COMMIT_CONTRACT = _terminal_contract.TERMINAL_SEMANTIC_COMMIT_CONTRACT
terminal_commit_outcome = _terminal_contract.terminal_commit_outcome
terminal_commit_projection_present = (
    _terminal_contract.terminal_commit_projection_present
)
terminal_projection_hash = _terminal_contract.projection_hash
_outcome_matches_semantic = _terminal_contract.outcome_matches_semantic

__all__ = [
    "LEGACY_TERMINAL_SEMANTIC_COMMIT_CONTRACT",
    "OPERATIONAL_TERMINAL_OUTCOMES",
    "TERMINAL_OUTCOMES",
    "TERMINAL_SEMANTIC_COMMIT_CONTRACT",
    "TerminalSemanticCommit",
    "build_terminal_semantic_commit",
    "canonical_terminal_semantic_answer",
    "terminal_commit_outcome",
    "terminal_commit_projection_present",
]


@dataclass(frozen=True, slots=True)
class TerminalSemanticCommit:
    """The one runtime-owned answer projection consumed by integrations.

    The nested values are copied on construction and on serialization.  The
    frozen wrapper prevents the runtime from replacing a committed answer,
    while callers still receive ordinary JSON-compatible dictionaries.
    """

    semantic_answer: str
    presentation_answer: str
    outcome: str
    outcome_reason: str
    answer_status: str
    verify_decision: dict[str, Any]
    guardrail_decision: dict[str, Any]
    authoritative_evidence: tuple[dict[str, Any], ...]
    citations: tuple[str, ...]
    projection_hash: str
    state_version: int = 3

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": TERMINAL_SEMANTIC_COMMIT_CONTRACT,
            "semantic_answer": self.semantic_answer,
            "presentation_answer": self.presentation_answer,
            "outcome": self.outcome,
            "outcome_reason": self.outcome_reason,
            "answer_status": self.answer_status,
            "verify_decision": deepcopy(self.verify_decision),
            "guardrail_decision": deepcopy(self.guardrail_decision),
            "authoritative_evidence": [
                deepcopy(item) for item in self.authoritative_evidence
            ],
            "citations": list(self.citations),
            "projection_hash": self.projection_hash,
            "state_version": self.state_version,
        }


def build_terminal_semantic_commit(
    answer: str,
    verify_decision: VerifyDecision | dict[str, Any],
    guardrail_decision: GuardrailDecision | dict[str, Any],
    bundle: EvidenceBundle | dict[str, Any],
    *,
    outcome: str | None = None,
    outcome_reason: str = "",
    presentation_answer: str | None = None,
) -> TerminalSemanticCommit:
    verify = _as_dict(verify_decision)
    guardrail = _as_dict(guardrail_decision)
    evidence_bundle = _as_dict(bundle)
    semantic_answer = canonical_terminal_semantic_answer(
        answer,
        verify,
        guardrail,
        evidence_bundle,
    )
    resolved_outcome = _terminal_outcome(
        outcome,
        semantic_answer,
        verify,
        guardrail,
    )
    if not _outcome_matches_semantic(resolved_outcome, semantic_answer):
        raise ValueError(
            f"Terminal outcome {resolved_outcome!r} does not match semantic answer"
        )
    resolved_reason = outcome_reason or _outcome_reason(
        resolved_outcome,
        verify,
        guardrail,
    )
    rendered_answer = str(
        answer if presentation_answer is None else presentation_answer
    )
    authoritative_evidence = (
        ()
        if resolved_outcome in OPERATIONAL_TERMINAL_OUTCOMES
        else tuple(_authoritative_evidence(evidence_bundle))
    )
    citations = (
        ()
        if resolved_outcome in OPERATIONAL_TERMINAL_OUTCOMES
        else tuple(
            str(value).strip()
            for value in verify.get("verified_citations") or []
            if str(value).strip()
        )
    )
    answer_status = "answered" if resolved_outcome == "answered" else "abstained"
    unsigned = {
        "contract_id": TERMINAL_SEMANTIC_COMMIT_CONTRACT,
        "semantic_answer": semantic_answer,
        "presentation_answer": rendered_answer,
        "outcome": resolved_outcome,
        "outcome_reason": resolved_reason,
        "answer_status": answer_status,
        "verify_decision": verify,
        "guardrail_decision": guardrail,
        "authoritative_evidence": list(authoritative_evidence),
        "citations": list(citations),
        "state_version": 3,
    }
    projection_hash = terminal_projection_hash(unsigned)
    return TerminalSemanticCommit(
        semantic_answer=semantic_answer,
        presentation_answer=rendered_answer,
        outcome=resolved_outcome,
        outcome_reason=resolved_reason,
        answer_status=answer_status,
        verify_decision=verify,
        guardrail_decision=guardrail,
        authoritative_evidence=authoritative_evidence,
        citations=citations,
        projection_hash=projection_hash,
    )


def canonical_terminal_semantic_answer(
    answer: str,
    verify_decision: VerifyDecision | dict[str, Any],
    guardrail_decision: GuardrailDecision | dict[str, Any],
    bundle: EvidenceBundle | dict[str, Any],
) -> str:
    """Choose the runtime-owned semantic answer before the terminal commit."""

    presentation_answer = str(answer or "")
    verify = _as_dict(verify_decision)
    guardrail = _as_dict(guardrail_decision)
    evidence_bundle = _as_dict(bundle)
    if _semantic_abstention(presentation_answer, verify, guardrail):
        return "unanswerable"
    verified_polarity = str(verify.get("canonical_answer_polarity") or "").lower()
    if verified_polarity in {"yes", "no"}:
        return verified_polarity
    if _planned_answer_type(evidence_bundle) == "boolean":
        candidate_polarity = canonical_boolean_answer_polarity(presentation_answer)
        if candidate_polarity:
            return candidate_polarity
    return presentation_answer


def _terminal_outcome(
    requested: str | None,
    semantic_answer: str,
    verify: dict[str, Any],
    guardrail: dict[str, Any],
) -> str:
    if requested is not None:
        normalized = str(requested).strip().lower()
        if normalized not in TERMINAL_OUTCOMES:
            raise ValueError(f"Unsupported terminal outcome: {requested}")
        return normalized
    return (
        "safe_abstention"
        if _semantic_abstention(semantic_answer, verify, guardrail)
        else "answered"
    )


def _outcome_reason(
    outcome: str,
    verify: dict[str, Any],
    guardrail: dict[str, Any],
) -> str:
    if outcome == "answered":
        return ""
    return str(guardrail.get("reason") or verify.get("reason") or outcome)


def _authoritative_evidence(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    values = metadata.get("verified_claim_support_evidence") or metadata.get(
        "verified_evidence"
    )
    return [dict(item) for item in values or [] if isinstance(item, dict)]


def _semantic_abstention(
    answer: str,
    verify: dict[str, Any],
    guardrail: dict[str, Any],
) -> bool:
    normalized = " ".join(answer.strip().lower().split())
    return bool(
        _incoherent_authority_projection(verify)
        or str(guardrail.get("action") or "").lower() == "abstain"
        or str(verify.get("action") or "").lower() == "abstain"
        or str(verify.get("status") or "").lower()
        in {"not_enough_evidence", "verified_conflict"}
        or normalized.startswith(
            (
                "unanswerable",
                "unknown",
                "insufficient evidence",
                "not enough evidence",
                "unable to answer",
                "cannot answer",
                ABSTAIN_MESSAGE.lower(),
            )
        )
    )


def _incoherent_authority_projection(verify: dict[str, Any]) -> bool:
    status = str(verify.get("status") or "").lower()
    typed = verify.get("typed_authority")
    typed = typed if isinstance(typed, dict) else {}
    typed_state = str(typed.get("state") or "").lower()
    exact_claim = any(
        str(result.get("authority_status") or "").lower()
        in {"exact", "composite_exact", "verified_support"}
        for result in verify.get("claim_results") or []
        if isinstance(result, dict)
    )
    return bool(
        (typed_state == "verified_support" and status != "supported")
        or (exact_claim and status not in {"supported", "verified_conflict"})
    )


def _planned_answer_type(bundle: dict[str, Any]) -> str:
    metadata = bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    plan = metadata.get("query_plan") or metadata.get("bound_query_plan")
    if not isinstance(plan, dict):
        return ""
    return str(plan.get("answer_type") or "").strip().lower()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        payload = as_dict()
        return deepcopy(payload) if isinstance(payload, dict) else {}
    return {}
