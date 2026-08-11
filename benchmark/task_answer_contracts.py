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
    QasperAnswerabilityResult,
    verify_qasper_answerability,
)
from .qasper_authority import required_authority_audit
from .qasper_candidate_state import (
    AnswerabilityCandidate,
    select_answerability_candidate,
)
from .qasper_evidence_priorities import (
    QasperEvidencePriorities,
    qasper_evidence_priorities,
)
from .qasper_support_binding import bind_answerability_support


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

    candidate_state = select_answerability_candidate(prediction)
    product_answer = candidate_state.product_answer
    pre_contract_verification = _verification_snapshot(
        prediction,
        answer=product_answer,
    )
    evidence_items = _prediction_evidence_items(prediction)
    result = _adjudicate_qasper_answer(
        prediction,
        candidate_state,
        evidence_items,
        llm_factory=llm_factory,
    )
    typed_boolean_recheck = result.trace.get("typed_boolean_recheck") == "true"
    answer_changed = _normalized_answer(result.answer) != _normalized_answer(
        product_answer
    )
    prediction["predicted_answer"] = result.answer
    recovery_result = _recovery_result(
        product_abstained=candidate_state.product_abstained,
        recovery_attempted=(
            candidate_state.recovery_attempted or typed_boolean_recheck
        ),
        final_answer=result.answer,
    )
    _record_answerability_result(
        metadata,
        candidate_state,
        result,
        recovery_result=recovery_result,
    )
    _refresh_qasper_verification(
        prediction,
        metadata,
        candidate_state,
        result,
        pre_contract_verification=pre_contract_verification,
    )
    _record_answerability_contract_trace(
        prediction,
        metadata,
        candidate_state,
        result,
        answer_changed=answer_changed,
        recovery_result=recovery_result,
        pre_contract_verification=pre_contract_verification,
    )
    prediction["task_answer_contract"] = {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": "applied",
    }
    return True


def synchronize_terminal_answer_state(prediction: dict[str, Any]) -> bool:
    """Commit one authoritative dataset state after presentation finalization."""

    from .finance_terminal_sync import is_finance_terminal_prediction
    from .finance_terminal_sync import (
        synchronize_terminal_answer_state as synchronize_finance,
    )

    if is_finance_terminal_prediction(prediction):
        return synchronize_finance(prediction)

    from .qasper_terminal_sync import synchronize_terminal_answer_state as synchronize

    return synchronize(
        prediction,
        clear_citations=_clear_stale_answer_citations,
        verify_answer=_run_post_contract_verification,
        bind_support=_bind_answerability_support,
    )


def _adjudicate_qasper_answer(
    prediction: dict[str, Any],
    candidate_state: AnswerabilityCandidate,
    evidence_items: list[dict[str, Any]],
    *,
    llm_factory: Callable[[], Any],
) -> QasperAnswerabilityResult:
    candidate = candidate_state.candidate_for_answerability
    question = str(prediction.get("question") or "")
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    priorities = qasper_evidence_priorities(
        prediction,
        evidence_items,
        question=question,
        candidate_answer="" if answer_type == "boolean" else candidate,
    )
    typed_boolean_recheck = bool(
        not candidate
        and answer_type == "boolean"
        and (
            priorities.required_evidence_ids
            or priorities.generation_evidence_ids
            or priorities.claim_support_evidence_ids
        )
    )
    if not candidate and not typed_boolean_recheck:
        authority_trace = (
            _missing_candidate_authority_trace(priorities)
            if answer_type == "boolean"
            else {}
        )
        return QasperAnswerabilityResult(
            answer=candidate_state.product_answer,
            trace={
                "contract_id": QASPER_ANSWERABILITY_CONTRACT,
                "status": "not_required",
                "verdict": "",
                "action": "preserved_product_abstention",
                "reason": "missing_original_candidate",
                **authority_trace,
            },
        )
    result = verify_qasper_answerability(
        llm_factory(),
        question=question,
        evidence=_prediction_evidence(prediction),
        evidence_items=evidence_items or None,
        required_evidence_ids=list(priorities.required_evidence_ids),
        required_slot_ids=list(priorities.required_slot_ids),
        missing_required_slot_ids=list(priorities.missing_required_slot_ids),
        missing_required_evidence_ids=list(priorities.missing_required_evidence_ids),
        priority_evidence_ids=list(priorities.generation_evidence_ids),
        claim_support_evidence_ids=list(priorities.claim_support_evidence_ids),
        claim_contradiction_evidence_ids=list(
            priorities.claim_contradiction_evidence_ids
        ),
        candidate_answer="unanswerable" if typed_boolean_recheck else candidate,
        answer_type=answer_type,
    )
    if not typed_boolean_recheck:
        return result
    return QasperAnswerabilityResult(
        answer=result.answer,
        trace={**result.trace, "typed_boolean_recheck": "true"},
    )


def _missing_candidate_authority_trace(
    priorities: QasperEvidencePriorities,
) -> dict[str, str]:
    return required_authority_audit(
        required=set(priorities.required_evidence_ids),
        selected_aliases=[],
        required_slot_ids=list(priorities.required_slot_ids),
        missing_required_slot_ids=list(priorities.missing_required_slot_ids),
        missing_required_evidence_ids=list(priorities.missing_required_evidence_ids),
    )


def _record_answerability_result(
    metadata: dict[str, Any],
    candidate_state: AnswerabilityCandidate,
    result: QasperAnswerabilityResult,
    *,
    recovery_result: str,
) -> None:
    metadata["qasper_answerability"] = {
        **result.trace,
        **_candidate_trace(candidate_state, result),
        "recovery_result": recovery_result,
        "final_post_contract_answer": result.answer,
    }


def _refresh_qasper_verification(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    candidate_state: AnswerabilityCandidate,
    result: QasperAnswerabilityResult,
    *,
    pre_contract_verification: dict[str, Any],
) -> None:
    if (
        not candidate_state.candidate_for_answerability
        and result.trace.get("typed_boolean_recheck") != "true"
    ):
        return
    prediction["pre_contract_verification"] = pre_contract_verification
    _clear_stale_answer_citations(prediction, metadata)
    _run_post_contract_verification(prediction, metadata, result.answer)
    _bind_answerability_support(
        prediction,
        metadata,
        answer=result.answer,
        trace=result.trace,
    )
    metadata["qasper_answerability"]["citation_state"] = "cleared_for_rebind"


def _record_answerability_contract_trace(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    candidate_state: AnswerabilityCandidate,
    result: QasperAnswerabilityResult,
    *,
    answer_changed: bool,
    recovery_result: str,
    pre_contract_verification: dict[str, Any],
) -> None:
    post_verification = (
        dict(prediction.get("post_contract_verification") or {})
        if answer_changed
        else _verification_snapshot(prediction, answer=result.answer)
    )
    metadata["answerability_contract_trace"] = {
        "pre_contract_answer": candidate_state.product_answer,
        "post_contract_answer": result.answer,
        "rewrite_applied": answer_changed,
        "rewrite_type": _rewrite_type(candidate_state.product_answer, result.answer),
        "rewrite_reason": _answerability_reason(result.trace),
        "pre_contract_verification": pre_contract_verification,
        "post_contract_verification": post_verification,
        **_candidate_trace(candidate_state, result),
        "recovery_result": recovery_result,
        "final_post_contract_answer": result.answer,
    }


def _candidate_trace(
    candidate_state: AnswerabilityCandidate,
    result: QasperAnswerabilityResult | None = None,
) -> dict[str, Any]:
    typed_boolean_recheck = bool(
        result is not None and result.trace.get("typed_boolean_recheck") == "true"
    )
    return {
        "input_candidate_kind": (
            "typed_boolean_proposition"
            if typed_boolean_recheck
            else candidate_state.input_candidate_kind
        ),
        "product_answer": candidate_state.product_answer,
        "pre_guardrail_answer": candidate_state.pre_guardrail_answer,
        "pre_verification_answer": candidate_state.pre_verification_answer,
        "candidate_for_answerability": candidate_state.candidate_for_answerability,
        "recovery_attempted": (
            candidate_state.recovery_attempted or typed_boolean_recheck
        ),
    }


def _answerability_reason(trace: dict[str, Any]) -> str:
    return str(
        trace.get("reason")
        or trace.get("action")
        or trace.get("verdict")
        or "answerability_contract_decision"
    )


def _recovery_result(
    *,
    product_abstained: bool,
    recovery_attempted: bool,
    final_answer: str,
) -> str:
    if not product_abstained:
        return "not_applicable"
    if not recovery_attempted:
        return "not_attempted"
    return "recovered" if not is_abstention_answer(final_answer) else "not_recovered"


def _bind_answerability_support(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    answer: str,
    trace: dict[str, Any],
) -> None:
    bind_answerability_support(
        prediction,
        metadata,
        answer=answer,
        trace=trace,
        evidence_items=_prediction_evidence_items(prediction),
    )


def _clear_stale_answer_citations(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    prediction["structured_citations"] = []
    prediction["predicted_citations"] = []
    prediction.pop("predicted_evidence", None)
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
        "verified_claim_support_spans",
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
            "verified_claim_support_spans",
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
        bundle = with_verification_evidence(bundle, decision, request=request)
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
