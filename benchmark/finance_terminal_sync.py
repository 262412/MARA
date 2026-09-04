from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .citation_rendering import citation_from_item
from .finance_citation_contract import authoritative_verified_claim_support
from .terminal_answer_state import rebuild_terminal_answer_state


def is_finance_terminal_prediction(prediction: dict[str, Any]) -> bool:
    if prediction.get("finance_citation_authority_status") in {
        "invalid",
        "verified_claim_support",
    }:
        return True
    contract = prediction.get("task_answer_contract")
    if isinstance(contract, dict) and str(contract.get("contract_id") or "").startswith(
        "financebench"
    ):
        return True
    for metadata in _existing_metadata_targets(prediction):
        plan = metadata.get("query_plan")
        if not isinstance(plan, dict):
            continue
        constraints = dict(plan.get("constraints") or {})
        if (
            str(constraints.get("verification_domain") or "").lower()
            in {
                "finance",
                "financial",
                "financebench",
            }
            and plan.get("state_authority") == "verified_claim_support.v1"
        ):
            return True
    return False


def synchronize_terminal_answer_state(prediction: dict[str, Any]) -> bool:
    """Commit a FinanceBench narrative answer from one verified plan state."""

    if not is_finance_terminal_prediction(prediction):
        return False
    authority = authoritative_verified_claim_support(prediction)
    if authority is None:
        _rebuild_abstention(prediction)
        return True
    support, plan = authority
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    ).strip()
    decision = _verify_decision(prediction)
    citations = [
        citation
        for item in support
        if (
            citation := citation_from_item(
                item,
                span=answer,
                canonical_sources=[],
                source_backrefs=[],
                evidence_identity=identity_of(item).key,
            )
        )
    ]
    if not citations or {
        str(citation.get("evidence_id") or "") for citation in citations
    } != {identity_of(item).key for item in support}:
        _rebuild_abstention(prediction)
        return True
    rebuild_terminal_answer_state(
        prediction,
        answer=answer,
        verify_decision=decision,
        claim_verification=dict(prediction.get("claim_verification") or {}),
        supporting_evidence=support,
        guardrail_decision={
            "status": "ok",
            "action": "return",
            "reason": "Terminal answer matches authoritative verified claim support.",
        },
        emitted_citations=citations,
    )
    for metadata in _metadata_targets(prediction):
        metadata["terminal_query_plan"] = dict(plan)
    return True


def _rebuild_abstention(prediction: dict[str, Any]) -> None:
    rebuild_terminal_answer_state(
        prediction,
        answer="unanswerable",
        verify_decision={
            "status": "not_enough_evidence",
            "action": "abstain",
            "reason": "Authoritative verified FinanceBench support is unavailable.",
        },
        claim_verification={
            "status": "not_enough_evidence",
            "claim_results": [],
        },
        supporting_evidence=[],
        guardrail_decision={
            "status": "not_enough_evidence",
            "action": "abstain",
            "reason": "Terminal answer has no authoritative verified support.",
        },
        emitted_citations=[],
    )
    _clear_abstained_query_plan_state(prediction)


def _clear_abstained_query_plan_state(prediction: dict[str, Any]) -> None:
    """Remove stale verified state while retaining the last retrieval binding."""

    for metadata in _metadata_targets(prediction):
        for key in ("query_plan", "bound_query_plan", "terminal_query_plan"):
            if not isinstance(metadata.get(key), dict):
                continue
            plan = dict(metadata[key])
            plan["state_authority"] = "abstained.v1"
            plan["evidence_slots"] = [
                _abstained_slot(slot)
                for slot in plan.get("evidence_slots") or []
                if isinstance(slot, dict)
            ]
            metadata[key] = plan
        if isinstance(metadata.get("verification_slot_states"), list):
            metadata["verification_slot_states"] = [
                _abstained_slot(state)
                for state in metadata["verification_slot_states"]
                if isinstance(state, dict)
            ]


def _abstained_slot(slot: dict[str, Any]) -> dict[str, Any]:
    state = dict(slot)
    evidence_ids = [
        str(evidence_id).strip()
        for evidence_id in state.get("evidence_ids") or []
        if str(evidence_id or "").strip()
    ]
    if evidence_ids and state.get("status") in {
        "filled",
        "retrieved_partial",
        "retrieved_unverified",
    }:
        state["evidence_ids"] = evidence_ids
        return state
    state["status"] = "missing"
    state["evidence_ids"] = []
    return state


def _metadata_targets(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = prediction.setdefault("evidence_metadata", {})
    targets = [metadata]
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.setdefault("metadata", {})
        if isinstance(bundle_metadata, dict) and bundle_metadata is not metadata:
            targets.append(bundle_metadata)
    return targets


def _existing_metadata_targets(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        targets.append(metadata)
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.get("metadata")
        if isinstance(bundle_metadata, dict) and bundle_metadata not in targets:
            targets.append(bundle_metadata)
    return targets


def _verify_decision(prediction: dict[str, Any]) -> dict[str, Any]:
    decision = prediction.get("verify_decision")
    if isinstance(decision, dict):
        return dict(decision)
    for metadata in _metadata_targets(prediction):
        decision = metadata.get("verify_decision")
        if isinstance(decision, dict):
            return dict(decision)
    return {}
