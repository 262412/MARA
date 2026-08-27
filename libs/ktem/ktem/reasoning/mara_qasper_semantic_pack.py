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
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_validation import (
    locally_observed_proposition_slots,
    semantic_relation_clause_analysis,
)

from .mara_qasper_candidate_evidence import candidate_evidence_set_binding
from .mara_semantic_proposition_packing import (
    SemanticPropositionEvidencePacking,
    semantic_proposition_pack_digest,
)


def prepare_qasper_canonical_records(
    question: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project records to the exact, locally checked selector universe."""

    proposition = build_question_proposition(question)
    applicable = applicable_proposition_evidence_slots(proposition)
    annotated: list[dict[str, Any]] = []
    for record in records:
        selectors: list[dict[str, Any]] = []
        for raw_selector in record.get("selectors") or []:
            selector = _canonical_selector(raw_selector, proposition, applicable)
            if selector is not None:
                selectors.append(selector)
        if selectors:
            annotated.append({**deepcopy(record), "selectors": selectors})
    observation = candidate_evidence_set_binding(annotated, question)
    selected_refs = set(observation.get("evidence_refs") or [])
    selected_refs.update(observation.get("support_evidence_refs") or [])
    selected_refs.update(observation.get("explicit_contradiction_evidence_refs") or [])
    if not selected_refs:
        selected_refs = {
            str(selector.get("selector_id") or "")
            for record in annotated
            for selector in record.get("selectors") or []
            if selector.get("candidate_relation_role") == "uncertainty_context"
            or (
                selector.get("candidate_relation_role") == "polarity_evidence"
                and "predicate" in set(selector.get("allowed_proposition_slots") or [])
            )
        }
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
    proposition: Any,
    applicable_slots: tuple[str, ...],
) -> dict[str, Any] | None:
    if not isinstance(raw_selector, dict):
        return None
    selector = deepcopy(raw_selector)
    text = str(selector.get("text") or "")
    analysis = semantic_relation_clause_analysis(
        {
            "quote": text,
            "binds_proposition_slots": list(applicable_slots),
        },
        proposition,
    )
    relation_bearing = analysis.get("relation_bearing") is True
    direct_negation = analysis.get("direct_relation_negated")
    direct_anchor = bool(
        relation_bearing
        and analysis.get("target_relation_present") is True
        and analysis.get("meta_scope") is not True
        and isinstance(direct_negation, bool)
    )
    raw_state = str(analysis.get("status") or "unbound")
    uncertainty_context = bool(
        not direct_anchor
        and raw_state in {"mention_only", "unbound"}
        and relation_bearing
        and analysis.get("target_relation_present") is True
    )
    allowed_slots = (
        []
        if uncertainty_context
        else list(locally_observed_proposition_slots(text, proposition))
    )
    if not allowed_slots and not uncertainty_context:
        return None
    if direct_anchor:
        local_state = (
            "explicit_contradiction" if direct_negation else "affirmative_assertion"
        )
    else:
        local_state = raw_state
    selector.update(
        allowed_proposition_slots=allowed_slots,
        relation_bearing=relation_bearing,
        candidate_relation_role=(
            "uncertainty_context" if uncertainty_context else "polarity_evidence"
        ),
        local_relation_state=local_state,
        local_relation_analysis_digest=str(analysis.get("analysis_digest") or ""),
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
    proposition = build_question_proposition(question)
    pack_digest = semantic_proposition_pack_digest(
        proposition,
        slots,
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
        slots=slots,
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
