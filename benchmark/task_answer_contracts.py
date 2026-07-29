from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.verification import verify_decision, with_verification_evidence

from .metrics import is_abstention_answer
from .qasper_answerability import (
    QASPER_ANSWERABILITY_CONTRACT,
    verify_qasper_answerability,
)


def apply_task_answer_contract(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    llm_factory: Callable[[], Any],
) -> bool:
    """Apply dataset answer invariants after engine output normalization.

    Returns ``True`` when the answer was adjudicated and finalization therefore
    needs to run again before scoring.
    """
    if "qasper" not in str(dataset_name or "").lower() or prediction.get("error"):
        return False
    metadata = prediction.setdefault("evidence_metadata", {})
    existing = metadata.get("qasper_answerability")
    if isinstance(existing, dict) and existing:
        prediction["task_answer_contract"] = {
            "contract_id": QASPER_ANSWERABILITY_CONTRACT,
            "status": "already_applied",
        }
        return False

    candidate = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    pre_contract_verification = _verification_snapshot(prediction, answer=candidate)
    evidence_items = _prediction_evidence_items(prediction)
    result = verify_qasper_answerability(
        llm_factory(),
        question=str(prediction.get("question") or ""),
        evidence=_prediction_evidence(prediction),
        evidence_items=evidence_items or None,
        required_evidence_ids=_required_plan_evidence_ids(prediction),
        candidate_answer=candidate,
    )
    answer_changed = _normalized_answer(result.answer) != _normalized_answer(candidate)
    prediction["predicted_answer"] = result.answer
    metadata["qasper_answerability"] = result.trace
    if answer_changed:
        prediction["pre_contract_verification"] = pre_contract_verification
        _clear_stale_answer_citations(prediction, metadata)
        _run_post_contract_verification(prediction, metadata, result.answer)
        metadata["qasper_answerability"]["citation_state"] = "cleared_for_rebind"
    post_contract_verification = (
        dict(prediction.get("post_contract_verification") or {})
        if answer_changed
        else _verification_snapshot(prediction, answer=result.answer)
    )
    metadata["answerability_contract_trace"] = {
        "pre_contract_answer": candidate,
        "post_contract_answer": result.answer,
        "rewrite_applied": answer_changed,
        "rewrite_type": _rewrite_type(candidate, result.answer),
        "rewrite_reason": str(
            result.trace.get("reason")
            or result.trace.get("action")
            or result.trace.get("verdict")
            or "answerability_contract_decision"
        ),
        "pre_contract_verification": pre_contract_verification,
        "post_contract_verification": post_contract_verification,
    }
    prediction["task_answer_contract"] = {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": "applied",
    }
    return True


def _clear_stale_answer_citations(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    prediction["structured_citations"] = []
    prediction["predicted_citations"] = []
    for key in (
        "verify_decision",
        "claim_verification",
        "guardrail_decision",
        "verifier_observability",
    ):
        prediction.pop(key, None)
    for key in (
        "cited_evidence",
        "emitted_citation_evidence",
        "verified_claim_support_evidence",
    ):
        metadata[key] = []
    for key in (
        "verified_evidence",
        "verify_decision",
        "claim_verification",
        "guardrail_decision",
        "verifier_observability",
    ):
        metadata.pop(key, None)
    metadata["answer_dependent_state"] = "invalidated_for_reverification"
    bundle = prediction.get("evidence_bundle")
    bundle_metadata = bundle.get("metadata") if isinstance(bundle, dict) else None
    if isinstance(bundle_metadata, dict):
        for key in (
            "cited_evidence",
            "emitted_citation_evidence",
            "verified_claim_support_evidence",
        ):
            bundle_metadata[key] = []
        for key in (
            "verified_evidence",
            "verify_decision",
            "claim_verification",
            "guardrail_decision",
            "verifier_observability",
        ):
            bundle_metadata.pop(key, None)
            bundle_metadata["answer_dependent_state"] = "invalidated_for_reverification"


def _verification_snapshot(
    prediction: dict[str, Any],
    *,
    answer: str,
) -> dict[str, Any]:
    snapshot = {
        key: prediction.get(key)
        for key in (
            "verify_decision",
            "claim_verification",
            "guardrail_decision",
            "verifier_observability",
        )
        if key in prediction
    }
    if snapshot:
        snapshot["answer"] = answer
    return snapshot


def _rewrite_type(before: str, after: str) -> str:
    if _normalized_answer(before) == _normalized_answer(after):
        return "none"
    before_abstained = is_abstention_answer(before)
    after_abstained = is_abstention_answer(after)
    if before_abstained and not after_abstained:
        return "unanswerable_to_polarity"
    if not before_abstained and after_abstained:
        return "polarity_to_unanswerable"
    return "answer_rewrite"


def _run_post_contract_verification(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    answer: str,
) -> None:
    normalized = _normalized_answer(answer)
    bundle = EvidenceBundle(
        route=str(prediction.get("route") or "benchmark"),
        items=_prediction_evidence_items(prediction),
        metadata={},
    )
    if normalized == "unanswerable":
        decision_payload = {
            "mode": "strict",
            "status": "not_enough_evidence",
            "reason": "QASPER answerability contract found insufficient evidence.",
            "action": "abstain",
            "claims": [],
            "unsupported_claims": [],
            "unknown_claims": [],
            "verified_citations": [],
            "claim_results": [],
        }
    else:
        request = DocQARequest(
            prompt=str(prediction.get("question") or ""),
            task_type=str(prediction.get("answer_type") or "free_text"),
            verification_mode="strict",
        )
        decision = verify_decision(
            request,
            SimpleNamespace(status="good", retry=False),
            bundle,
            answer,
        )
        decision_payload = decision.as_dict()
        bundle = with_verification_evidence(bundle, decision)
    prediction["verify_decision"] = decision_payload
    prediction["claim_verification"] = {
        "contract_id": "post_task_answer_verification.v1",
        "status": decision_payload["status"],
        "claim_results": list(decision_payload.get("claim_results") or []),
        "unsupported_claims": list(decision_payload.get("unsupported_claims") or []),
        "unknown_claims": list(decision_payload.get("unknown_claims") or []),
    }
    prediction["post_contract_verification"] = {
        "contract_id": "post_task_answer_verification.v1",
        "answer": answer,
        "status": decision_payload["status"],
        "verify_decision": decision_payload,
    }
    metadata_targets = [metadata]
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        bundle_metadata = evidence_bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            metadata_targets.append(bundle_metadata)
    for target in metadata_targets:
        target["verify_decision"] = decision_payload
        target["claim_verification"] = prediction["claim_verification"]
        target["answer_dependent_state"] = "post_contract_verified"
        for key in (
            "verified_evidence",
            "verified_claim_support_evidence",
            "verified_claim_support_by_claim",
        ):
            if key in bundle.metadata:
                target[key] = bundle.metadata[key]


def _prediction_evidence_items(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        for key in (
            "generation_context_evidence",
            "selected_evidence",
            "reranked_evidence",
            "canonical_candidate_evidence",
            "evidence",
        ):
            items.extend(_records(metadata.get(key)))
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        items.extend(_records(bundle.get("items")))
    items.extend(_records(prediction.get("retrieved_hits")))
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        try:
            identity = identity_of(item).key
        except ValueError:
            continue
        if identity in seen:
            continue
        seen.add(identity)
        output.append(item)
    return output


def _required_plan_evidence_ids(prediction: dict[str, Any]) -> list[str]:
    metadata = prediction.get("evidence_metadata")
    payload = metadata.get("query_plan") if isinstance(metadata, dict) else None
    if not isinstance(payload, dict):
        bundle = prediction.get("evidence_bundle")
        bundle_metadata = bundle.get("metadata") if isinstance(bundle, dict) else None
        payload = (
            bundle_metadata.get("query_plan")
            if isinstance(bundle_metadata, dict)
            else None
        )
    if not isinstance(payload, dict):
        return []
    values: list[str] = []
    for slot in payload.get("evidence_slots") or []:
        if not isinstance(slot, dict) or not any(
            bool(slot.get(field))
            for field in (
                "required",
                "required_for_retrieval",
                "required_for_execution",
                "required_for_verification",
            )
        ):
            continue
        for evidence_id in slot.get("evidence_ids") or []:
            value = str(evidence_id).strip()
            if value and value not in values:
                values.append(value)
    return values


def _normalized_answer(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _prediction_evidence(prediction: dict[str, Any]) -> str:
    values: list[str] = []
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        values.extend(_item_text(item) for item in _records(bundle.get("items")))
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        values.extend(_item_text(item) for item in _records(metadata.get("evidence")))
    values.extend(
        _item_text(item) for item in _records(prediction.get("retrieved_hits"))
    )
    values.append(str(prediction.get("context_preview") or ""))
    return "\n\n".join(dict.fromkeys(value for value in values if value.strip()))


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )
