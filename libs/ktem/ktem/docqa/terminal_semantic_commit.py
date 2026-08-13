from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .boolean_claim_verification import canonical_boolean_answer_polarity
from .evidence import EvidenceBundle
from .execution_contracts import ABSTAIN_MESSAGE
from .execution_models import GuardrailDecision
from .verification import VerifyDecision

TERMINAL_SEMANTIC_COMMIT_CONTRACT = "terminal_semantic_commit.v2"


@dataclass(frozen=True, slots=True)
class TerminalSemanticCommit:
    """The one runtime-owned answer projection consumed by integrations.

    The nested values are copied on construction and on serialization.  The
    frozen wrapper prevents the runtime from replacing a committed answer,
    while callers still receive ordinary JSON-compatible dictionaries.
    """

    semantic_answer: str
    answer_status: str
    verify_decision: dict[str, Any]
    guardrail_decision: dict[str, Any]
    authoritative_evidence: tuple[dict[str, Any], ...]
    citations: tuple[str, ...]
    projection_hash: str
    state_version: int = 2

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": TERMINAL_SEMANTIC_COMMIT_CONTRACT,
            "semantic_answer": self.semantic_answer,
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
    authoritative_evidence = tuple(_authoritative_evidence(evidence_bundle))
    citations = tuple(
        str(value).strip()
        for value in verify.get("verified_citations") or []
        if str(value).strip()
    )
    answer_status = _answer_status(semantic_answer, verify, guardrail)
    unsigned = {
        "contract_id": TERMINAL_SEMANTIC_COMMIT_CONTRACT,
        "semantic_answer": semantic_answer,
        "answer_status": answer_status,
        "verify_decision": verify,
        "guardrail_decision": guardrail,
        "authoritative_evidence": list(authoritative_evidence),
        "citations": list(citations),
        "state_version": 2,
    }
    projection_hash = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return TerminalSemanticCommit(
        semantic_answer=semantic_answer,
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


def terminal_commit_projection_present(
    commit: Any,
) -> bool:
    if not isinstance(commit, dict):
        return False
    if commit.get("contract_id") != TERMINAL_SEMANTIC_COMMIT_CONTRACT:
        return False
    expected = dict(commit)
    projection_hash = str(expected.pop("projection_hash") or "")
    if not projection_hash:
        return False
    computed = hashlib.sha256(
        json.dumps(
            expected,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return computed == projection_hash


def _authoritative_evidence(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    values = metadata.get("verified_claim_support_evidence") or metadata.get(
        "verified_evidence"
    )
    return [dict(item) for item in values or [] if isinstance(item, dict)]


def _answer_status(
    answer: str,
    verify: dict[str, Any],
    guardrail: dict[str, Any],
) -> str:
    return (
        "abstained" if _semantic_abstention(answer, verify, guardrail) else "answered"
    )


def _semantic_abstention(
    answer: str,
    verify: dict[str, Any],
    guardrail: dict[str, Any],
) -> bool:
    normalized = " ".join(answer.strip().lower().split())
    return bool(
        str(guardrail.get("action") or "").lower() == "abstain"
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
