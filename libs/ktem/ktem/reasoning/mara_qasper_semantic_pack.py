from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY,
    canonical_payload_digest,
    qasper_canonical_records_reason,
    qasper_canonical_span_universe_digest,
)
from ktem.docqa.question_proposition import build_question_proposition

from .mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_required_slots_from_binding,
)
from .mara_qasper_candidate_evidence_projection import exact_selector_valid
from .mara_qasper_candidate_selector_semantics import revalidated_selector_semantics
from .mara_semantic_proposition_packing import (
    SemanticPropositionEvidencePacking,
    semantic_proposition_pack_digest,
)


def prepare_qasper_canonical_records(
    question: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project records to the exact, locally checked selector universe."""

    annotated: list[dict[str, Any]] = []
    for record in records:
        selectors: list[dict[str, Any]] = []
        for raw_selector in record.get("selectors") or []:
            selector = _canonical_selector(raw_selector, record, question)
            if selector is not None:
                selectors.append(selector)
        if selectors:
            annotated.append({**deepcopy(record), "selectors": selectors})
    observation = candidate_evidence_set_binding(annotated, question)
    selected_refs = set(observation.get("selector_universe_refs") or [])
    return [
        {**record, "selectors": selected}
        for record in annotated
        if (
            selected := [
                selector
                for selector in record.get("selectors") or []
                if str(selector.get("selector_id") or "") in selected_refs
            ]
        )
    ]


def _canonical_selector(
    raw_selector: Any,
    record: dict[str, Any],
    question: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_selector, dict) or not exact_selector_valid(
        raw_selector,
        record_text=record.get("text"),
        record_text_start=record.get("text_start"),
    ):
        return None
    selector = deepcopy(raw_selector)
    text = str(selector.get("text") or "")
    semantics = revalidated_selector_semantics(selector, question, text)
    allowed_slots = list(semantics["slots"])
    uncertainty_context = semantics["candidate_relation_role"] == (
        "uncertainty_context"
    )
    if not allowed_slots and not uncertainty_context:
        return None
    selector.update(
        allowed_proposition_slots=allowed_slots,
        proposition_slot_spans=deepcopy(semantics["slot_spans"]),
        relation_bearing=bool(semantics["relation_bearing"]),
        candidate_relation_role=str(semantics["candidate_relation_role"]),
        local_relation_state=str(semantics["local_relation_state"]),
        local_relation_analysis_digest=str(semantics["local_relation_analysis_digest"]),
    )
    return selector


def freeze_qasper_canonical_semantic_pack(
    bundle: EvidenceBundle,
    *,
    question: str,
    slots: list[dict[str, Any]],
    source_packing: SemanticPropositionEvidencePacking,
    records: list[dict[str, Any]],
    candidate_transaction_id: str,
    candidate_binding: dict[str, Any] | None = None,
    candidate_required_slots: list[dict[str, Any]] | None = None,
) -> SemanticPropositionEvidencePacking:
    """Freeze the exact semantic object seen by one QASPER candidate.

    The stored records are the post-budget records used in the candidate message,
    not a fresh projection from the retrieval bundle.  Later stages can validate
    and reuse this value, but cannot extend it in place.
    """

    canonical_records = deepcopy(records)
    records_reason = qasper_canonical_records_reason(canonical_records)
    if records_reason:
        raise ValueError(records_reason)
    if (
        prepare_qasper_canonical_records(question, canonical_records)
        != canonical_records
    ):
        raise ValueError("canonical_semantic_pack_proposition_binding_mismatch")
    authoritative_binding = candidate_evidence_set_binding(
        canonical_records,
        question,
    )
    if candidate_binding is not None and candidate_binding != authoritative_binding:
        raise ValueError("canonical_semantic_pack_binding_inconsistent")
    canonical_slots = candidate_required_slots_from_binding(
        slots,
        authoritative_binding,
    )
    if (
        candidate_required_slots is not None
        and candidate_required_slots != canonical_slots
    ):
        raise ValueError("canonical_semantic_pack_binding_inconsistent")
    proposition = build_question_proposition(question)
    pack_digest = semantic_proposition_pack_digest(
        proposition,
        canonical_slots,
        canonical_records,
        item_char_limit=source_packing.item_char_limit,
    )
    packing = SemanticPropositionEvidencePacking(
        records=canonical_records,
        item_char_limit=source_packing.item_char_limit,
        input_token_budget=source_packing.input_token_budget,
        estimated_input_tokens=source_packing.estimated_input_tokens,
        dropped_count=source_packing.dropped_count,
        truncated_count=source_packing.truncated_count,
        semantic_pack_digest=pack_digest,
        question_proposition=deepcopy(source_packing.question_proposition),
        question_proposition_resolution=deepcopy(
            source_packing.question_proposition_resolution
        ),
    )
    payload = _pack_payload(
        packing,
        question=question,
        slots=canonical_slots,
        proposition_binding=authoritative_binding,
        candidate_transaction_id=candidate_transaction_id,
    )
    payload["pack_identity_digest"] = canonical_payload_digest(payload)
    bundle.metadata[QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY] = payload
    return packing


def load_qasper_canonical_semantic_pack(
    bundle: EvidenceBundle,
    *,
    question: str,
    candidate_transaction_id: str = "",
) -> tuple[SemanticPropositionEvidencePacking | None, str]:
    """Load one frozen pack after validating every persisted identity field."""

    raw = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw, dict):
        return None, "canonical_semantic_pack_missing"
    payload = deepcopy(raw)
    identity_digest = str(payload.pop("pack_identity_digest", "") or "")
    if (
        payload.get("contract_id") != QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT
        or not identity_digest
        or canonical_payload_digest(payload) != identity_digest
        or str(payload.get("question_digest") or "")
        != canonical_payload_digest(question.strip())
    ):
        return None, "canonical_semantic_pack_identity_mismatch"
    stored_transaction = str(payload.get("candidate_transaction_id") or "")
    if candidate_transaction_id and stored_transaction != candidate_transaction_id:
        return None, "canonical_semantic_pack_candidate_transaction_mismatch"
    records = payload.get("records")
    slots = payload.get("slots")
    if not isinstance(records, list) or not isinstance(slots, list):
        return None, "canonical_semantic_pack_identity_mismatch"
    records_reason = qasper_canonical_records_reason(records)
    if records_reason:
        return None, records_reason
    if prepare_qasper_canonical_records(question, records) != records:
        return None, "canonical_semantic_pack_proposition_binding_mismatch"
    proposition_binding = candidate_evidence_set_binding(records, question)
    if (
        payload.get("proposition_binding") != proposition_binding
        or str(payload.get("proposition_binding_digest") or "")
        != str(proposition_binding.get("binding_digest") or "")
        or candidate_required_slots_from_binding(slots, proposition_binding) != slots
    ):
        return None, "canonical_semantic_pack_proposition_binding_mismatch"
    span_digest = qasper_canonical_span_universe_digest(records)
    if span_digest != str(payload.get("span_universe_digest") or ""):
        return None, "canonical_semantic_pack_identity_mismatch"
    item_char_limit = _nonnegative_int(payload.get("item_char_limit"))
    integer_fields: dict[str, int] = {}
    for key in (
        "input_token_budget",
        "estimated_input_tokens",
        "dropped_count",
        "truncated_count",
    ):
        value = _nonnegative_int(payload.get(key))
        if value is None:
            return None, "canonical_semantic_pack_identity_mismatch"
        integer_fields[key] = value
    if item_char_limit is None:
        return None, "canonical_semantic_pack_identity_mismatch"
    recomputed_pack_digest = semantic_proposition_pack_digest(
        build_question_proposition(question),
        slots,
        records,
        item_char_limit=item_char_limit,
    )
    if recomputed_pack_digest != str(payload.get("semantic_pack_digest") or ""):
        return None, "canonical_semantic_pack_identity_mismatch"
    packing = SemanticPropositionEvidencePacking(
        records=records,
        item_char_limit=item_char_limit,
        input_token_budget=integer_fields["input_token_budget"],
        estimated_input_tokens=integer_fields["estimated_input_tokens"],
        dropped_count=integer_fields["dropped_count"],
        truncated_count=integer_fields["truncated_count"],
        semantic_pack_digest=recomputed_pack_digest,
        question_proposition=deepcopy(payload.get("question_proposition") or {}),
        question_proposition_resolution=deepcopy(
            payload.get("question_proposition_resolution") or {}
        ),
    )
    return packing, ""


def qasper_canonical_required_slots(
    bundle: EvidenceBundle,
) -> list[dict[str, Any]]:
    """Return slots from a pack already accepted by the canonical loader."""

    raw = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw, dict) or not isinstance(raw.get("slots"), list):
        raise ValueError("canonical_semantic_pack_identity_mismatch")
    return deepcopy(raw["slots"])


def qasper_canonical_selector_bindings(
    records: list[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    return {
        str(selector.get("selector_id") or ""): tuple(
            str(slot) for slot in selector.get("allowed_proposition_slots") or []
        )
        for record in records
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
        and str(selector.get("selector_id") or "")
        and selector.get("allowed_proposition_slots")
    }


def _pack_payload(
    packing: SemanticPropositionEvidencePacking,
    *,
    question: str,
    slots: list[dict[str, Any]],
    proposition_binding: dict[str, Any],
    candidate_transaction_id: str,
) -> dict[str, Any]:
    return {
        "contract_id": QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
        "candidate_transaction_id": str(candidate_transaction_id or ""),
        "question_digest": canonical_payload_digest(question.strip()),
        "semantic_pack_digest": packing.semantic_pack_digest,
        "span_universe_digest": qasper_canonical_span_universe_digest(packing.records),
        "records": deepcopy(packing.records),
        "slots": deepcopy(slots),
        "proposition_binding": deepcopy(proposition_binding),
        "proposition_binding_digest": str(
            proposition_binding.get("binding_digest") or ""
        ),
        "item_char_limit": packing.item_char_limit,
        "input_token_budget": packing.input_token_budget,
        "estimated_input_tokens": packing.estimated_input_tokens,
        "dropped_count": packing.dropped_count,
        "truncated_count": packing.truncated_count,
        "question_proposition": deepcopy(packing.question_proposition),
        "question_proposition_resolution": deepcopy(
            packing.question_proposition_resolution
        ),
        "immutable_after_candidate_generation": True,
    }


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
