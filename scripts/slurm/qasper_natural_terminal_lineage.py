from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa.boolean_verification_projection import project_boolean_assessment
from ktem.docqa.candidate_verification_policy import finish_candidate_decision
from ktem.docqa.engine_terminal_projection import engine_terminal_projection
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_models import GuardrailDecision
from ktem.docqa.verification import with_verification_evidence


def typed_authority_terminal_observation(
    request: Any,
    authority: Any,
    bundle: EvidenceBundle,
    *,
    question: str,
    candidate: str,
) -> dict[str, Any]:
    if authority is None:
        return _missing_terminal_authority("semantic_authority_not_bound")
    semantic = project_boolean_assessment(authority)
    typed = finish_candidate_decision(
        request,
        SimpleNamespace(status="good"),
        bundle,
        answer=candidate,
        mode="strict",
        candidate=candidate,
        prompt=question,
        domain="qasper",
        typed_boolean=semantic,
        semantic=semantic,
    )
    if typed is None:
        return _missing_terminal_authority("typed_authority_not_resolved")
    verified_bundle = with_verification_evidence(bundle, typed, request)
    terminal_answer, commit = _terminal_commit(candidate, typed, verified_bundle)
    verified_ids = _canonical_evidence_ids(
        verified_bundle.metadata.get("verified_claim_support_evidence")
    )
    authoritative_ids = _canonical_evidence_ids(commit.get("authoritative_evidence"))
    citations = [str(value) for value in commit.get("citations") or []]
    typed_citations = [str(value) for value in typed.verified_citations]
    typed_authority = _mapping(typed.typed_authority)
    lineage_closed = bool(
        typed.status == "supported"
        and typed_authority.get("state") == "verified_support"
        and typed_citations
        and typed_citations == verified_ids == authoritative_ids == citations
        and terminal_answer == str(typed.canonical_answer_polarity or candidate)
        and commit.get("outcome") == "answered"
    )
    return {
        "called": True,
        "status": typed.status,
        "reason": typed.reason,
        "typed_authority_state": str(typed_authority.get("state") or ""),
        "typed_authority_reason": str(typed_authority.get("reason") or ""),
        "typed_authority_contract_id": str(typed_authority.get("contract_id") or ""),
        "slot_bindings": deepcopy(_mapping(typed_authority.get("slot_bindings"))),
        "verified_citations": typed_citations,
        "verified_evidence_ids": verified_ids,
        "terminal_answer": terminal_answer,
        "terminal_outcome": str(commit.get("outcome") or ""),
        "terminal_citations": citations,
        "terminal_authoritative_evidence_ids": authoritative_ids,
        "query_plan_state_version": int(
            getattr(request, "query_plan_state_version", 0) or 0
        ),
        "citation_terminal_lineage_closed": lineage_closed,
    }


def _terminal_commit(
    candidate: str,
    typed: Any,
    verified_bundle: EvidenceBundle,
) -> tuple[str, dict[str, Any]]:
    guardrail = GuardrailDecision(
        status="ok",
        action="return",
        reason="frozen canonical authority verified",
    )
    terminal_answer, terminal_state, *_rest = engine_terminal_projection(
        candidate,
        typed,
        guardrail,
        verified_bundle,
        raw_generated_answer=candidate,
    )
    return terminal_answer, _mapping(terminal_state.get("terminal_semantic_commit"))


def _canonical_evidence_ids(value: Any) -> list[str]:
    return [identity_of(item).key for item in value or [] if isinstance(item, dict)]


def _missing_terminal_authority(reason: str) -> dict[str, Any]:
    return {
        "called": False,
        "status": "missing",
        "reason": reason,
        "typed_authority_state": "",
        "typed_authority_reason": reason,
        "typed_authority_contract_id": "",
        "slot_bindings": {},
        "verified_citations": [],
        "verified_evidence_ids": [],
        "terminal_answer": "",
        "terminal_outcome": "",
        "terminal_citations": [],
        "terminal_authoritative_evidence_ids": [],
        "query_plan_state_version": 0,
        "citation_terminal_lineage_closed": False,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
