from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of

from .metrics import is_abstention_answer
from .qasper_boolean_scope import scope_valid_support_items
from .qasper_deterministic_support import deterministic_support_ids


def bind_answerability_support(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    answer: str,
    trace: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> None:
    if is_abstention_answer(answer):
        return
    quote = str(trace.get("evidence_quote") or "").strip()
    if str(trace.get("quote_grounded") or "").lower() != "true" or not quote:
        return
    authority_ids = _answerability_authority_ids(trace)
    alias_lookup = unambiguous_evidence_alias_lookup(evidence_items)
    authoritative_items = [
        alias_lookup[evidence_id]
        for evidence_id in authority_ids
        if evidence_id in alias_lookup
    ]
    items = authoritative_items or [
        item
        for item in evidence_items
        if _normalized_answer(quote) in _normalized_answer(_item_text(item))
    ]
    if str(prediction.get("answer_type") or "").strip().lower() == "boolean":
        items = _validated_boolean_support(prediction, answer, trace, items)
    if not items:
        return
    support = min(items, key=lambda item: len(_item_text(item)))
    support_id = identity_of(support).key
    prediction["predicted_evidence"] = [_item_text(support)]
    support_span = str(trace.get("authoritative_quote_span_id") or "").strip()
    support_spans = [support_span] if support_span else []
    question = str(prediction.get("question") or "")
    claim = (
        f"{_normalized_answer(answer)}: {question}"
        if str(prediction.get("answer_type") or "").strip().lower() == "boolean"
        else answer
    )
    decision_payload = _supported_decision_payload(claim, support_id, support_spans)
    prediction["verify_decision"] = decision_payload
    prediction["claim_verification"] = {
        "contract_id": "qasper_typed_post_contract_verification.v1",
        "status": "supported",
        "claim_results": decision_payload["claim_results"],
        "unsupported_claims": [],
        "unknown_claims": [],
    }
    prediction["post_contract_verification"] = {
        "contract_id": "qasper_typed_post_contract_verification.v1",
        "answer": answer,
        "status": "supported",
        "verify_decision": decision_payload,
    }
    targets = [metadata]
    bundle = prediction.get("evidence_bundle")
    bundle_metadata = bundle.get("metadata") if isinstance(bundle, dict) else None
    if isinstance(bundle_metadata, dict):
        targets.append(bundle_metadata)
    for target in targets:
        target["verify_decision"] = decision_payload
        target["claim_verification"] = prediction["claim_verification"]
        target["verified_evidence"] = [support]
        target["verified_claim_support_evidence"] = [support]
        target["verified_claim_support_by_claim"] = {
            "qasper:answerability": [support_id]
        }
        target["verified_claim_support_spans"] = support_spans
        target["answer_dependent_state"] = "post_contract_verified"


def _supported_decision_payload(
    claim: str,
    support_id: str,
    support_spans: list[str],
) -> dict[str, Any]:
    return {
        "mode": "strict",
        "status": "supported",
        "reason": "QASPER typed answerability grounded the final claim.",
        "action": "return",
        "claims": [claim],
        "unsupported_claims": [],
        "unknown_claims": [],
        "verified_citations": [support_id],
        "claim_results": [
            {
                "claim_id": "qasper:answerability",
                "claim": claim,
                "status": "supported",
                "supporting_evidence_ids": [support_id],
                "supporting_evidence_spans": support_spans,
                "contradicting_evidence_ids": [],
            }
        ],
    }


def _validated_boolean_support(
    prediction: dict[str, Any],
    answer: str,
    trace: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    authority_ids = set(_answerability_authority_ids(trace))
    if authority_ids:
        return [item for item in items if identity_of(item).key in authority_ids]
    deterministic_ids = deterministic_support_ids(trace)
    if deterministic_ids:
        return [item for item in items if identity_of(item).key in deterministic_ids]
    return scope_valid_support_items(
        str(prediction.get("question") or ""),
        answer,
        items,
    )


def _answerability_authority_ids(trace: dict[str, Any]) -> list[str]:
    values: list[str] = []
    direct = str(trace.get("authoritative_quote_evidence_id") or "").strip()
    if direct:
        values.append(direct)
    for key in ("bound_support_evidence_ids", "final_support_evidence_ids"):
        raw = trace.get(key)
        if isinstance(raw, list):
            values.extend(str(value).strip() for value in raw if str(value).strip())
        elif isinstance(raw, str):
            values.extend(value.strip() for value in raw.split(",") if value.strip())
    return list(dict.fromkeys(values))


def _normalized_answer(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )
