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
from .mara_qasper_candidate_plan_metadata import candidate_selector_plan_metadata
from .mara_qasper_candidate_selector_semantics import (
    build_local_selector_semantic_alignment,
    revalidated_selector_semantics,
)
from .mara_qasper_semantic_pack_observation import mapping as _mapping
from .mara_qasper_semantic_pack_observation import mapping_list as _mapping_list
from .mara_qasper_semantic_pack_observation import (
    source_packing_observation as _source_packing_observation,
)
from .mara_qasper_semantic_pack_observation import (
    source_records_from_payload as _source_records_from_payload,
)
from .mara_qasper_semantic_pack_trace import canonical_selector_projection_trace
from .mara_semantic_proposition_packing import (
    SemanticPropositionEvidencePacking,
    semantic_proposition_pack_digest,
)


def prepare_qasper_canonical_records(
    question: str,
    records: list[dict[str, Any]],
    *,
    candidate_transaction_id: str = "",
) -> list[dict[str, Any]]:
    """Project records to the exact, locally checked selector universe."""

    projected, _trace = prepare_qasper_canonical_records_with_trace(
        question,
        records,
        candidate_transaction_id=candidate_transaction_id,
    )
    return projected


def prepare_qasper_canonical_records_with_trace(
    question: str,
    records: list[dict[str, Any]],
    *,
    candidate_transaction_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project canonical records and retain every selector disposition."""

    annotated: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        selectors: list[dict[str, Any]] = []
        for selector_index, raw_selector in enumerate(
            record.get("selectors") or [],
            start=1,
        ):
            selector, reason = _canonical_selector_projection(
                raw_selector,
                record,
                question,
            )
            decisions.append(
                {
                    "record_index": record_index,
                    "source_selector_index": selector_index,
                    "evidence_id": str(record.get("evidence_id") or ""),
                    "selector_ref": (
                        str(raw_selector.get("selector_id") or "")
                        if isinstance(raw_selector, dict)
                        else ""
                    ),
                    "decision": "eligible" if selector is not None else "rejected",
                    "reason": reason,
                }
            )
            if selector is not None:
                selectors.append(selector)
        if selectors:
            annotated.append({**deepcopy(record), "selectors": selectors})
    observation = candidate_evidence_set_binding(
        annotated,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    selected_refs = set(observation.get("selector_universe_refs") or [])
    projected = [
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
    selected_identities = {
        (str(record.get("evidence_id") or ""), str(selector.get("selector_id") or ""))
        for record in projected
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
    }
    for decision in decisions:
        identity = (decision["evidence_id"], decision["selector_ref"])
        if decision["decision"] == "eligible":
            is_selected = identity in selected_identities
            decision["decision"] = "selected" if is_selected else "rejected"
            decision["reason"] = (
                "selected_for_canonical_selector_universe"
                if is_selected
                else "not_in_canonical_selector_universe"
            )
    trace = canonical_selector_projection_trace(
        records,
        projected,
        decisions,
        observation,
        selected_identities,
    )
    return projected, trace


def _canonical_records_match(
    question: str,
    records: list[dict[str, Any]],
    candidate_transaction_id: str,
) -> bool:
    return (
        prepare_qasper_canonical_records(
            question,
            records,
            candidate_transaction_id=candidate_transaction_id,
        )
        == records
    )


def _canonical_selector_projection(
    raw_selector: Any,
    record: dict[str, Any],
    question: str,
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(raw_selector, dict) or not exact_selector_valid(
        raw_selector,
        record_text=record.get("text"),
        record_text_start=record.get("text_start"),
    ):
        return None, "exact_selector_invalid"
    selector = deepcopy(raw_selector)
    selector.pop("semantic_alignment", None)
    selector.pop("predicate_match_kind", None)
    text = str(selector.get("text") or "")
    semantics = revalidated_selector_semantics(selector, question, text)
    initial_metadata = candidate_selector_plan_metadata(
        record,
        selector,
        question,
        semantics,
    )
    selector.update(
        evidence_id=str(record.get("evidence_id") or ""),
        event_id=initial_metadata["event_id"],
        predicate_match_kind=initial_metadata["predicate_match_kind"],
        slot_hints=list(semantics["slots"]),
        local_relation_state=str(semantics["local_relation_state"]),
    )
    alignment = build_local_selector_semantic_alignment(
        question,
        selector,
        semantics,
    )
    if alignment is not None:
        selector["semantic_alignment"] = alignment
        selector["slot_hints"] = list(alignment["slot_refs"])
        semantics = revalidated_selector_semantics(selector, question, text)
    allowed_slots = list(semantics["slots"])
    uncertainty_context = semantics["candidate_relation_role"] == (
        "uncertainty_context"
    )
    if not allowed_slots and not uncertainty_context:
        return None, "slotless_non_uncertainty"
    selector.update(
        allowed_proposition_slots=allowed_slots,
        proposition_slot_spans=deepcopy(semantics["slot_spans"]),
        relation_bearing=bool(semantics["relation_bearing"]),
        candidate_relation_role=str(semantics["candidate_relation_role"]),
        local_relation_state=str(semantics["local_relation_state"]),
        local_relation_analysis_digest=str(semantics["local_relation_analysis_digest"]),
        **candidate_selector_plan_metadata(
            record,
            selector,
            question,
            semantics,
        ),
    )
    return selector, "locally_auditable_selector"


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
    if not _canonical_records_match(
        question,
        canonical_records,
        candidate_transaction_id,
    ):
        raise ValueError("canonical_semantic_pack_proposition_binding_mismatch")
    authoritative_binding = candidate_evidence_set_binding(
        canonical_records,
        question,
        candidate_transaction_id=candidate_transaction_id,
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
    packing = _build_frozen_packing(
        source_packing,
        records=canonical_records,
        semantic_pack_digest=pack_digest,
    )
    payload = _pack_payload(
        packing,
        question=question,
        slots=canonical_slots,
        proposition_binding=authoritative_binding,
        candidate_transaction_id=candidate_transaction_id,
    )
    payload["source_packing_observation"] = _source_packing_observation(
        source_packing,
        canonical_records=packing.records,
        canonical_semantic_pack_digest=packing.semantic_pack_digest,
    )
    payload["pack_identity_digest"] = canonical_payload_digest(payload)
    bundle.metadata[QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY] = payload
    return packing


def _build_frozen_packing(
    source_packing: SemanticPropositionEvidencePacking,
    *,
    records: list[dict[str, Any]],
    semantic_pack_digest: str,
) -> SemanticPropositionEvidencePacking:
    return SemanticPropositionEvidencePacking(
        records=records,
        source_records=deepcopy(source_packing.source_records),
        item_char_limit=source_packing.item_char_limit,
        input_token_budget=source_packing.input_token_budget,
        estimated_input_tokens=source_packing.estimated_input_tokens,
        dropped_count=source_packing.dropped_count,
        truncated_count=source_packing.truncated_count,
        semantic_pack_digest=semantic_pack_digest,
        question_proposition=deepcopy(source_packing.question_proposition),
        question_proposition_resolution=deepcopy(
            source_packing.question_proposition_resolution
        ),
        source_decisions=deepcopy(source_packing.source_decisions),
        window_decisions=deepcopy(source_packing.window_decisions),
        source_input_snapshot=deepcopy(source_packing.source_input_snapshot),
    )


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
    if not _canonical_records_match(question, records, stored_transaction):
        return None, "canonical_semantic_pack_proposition_binding_mismatch"
    if _stored_binding_reason(
        payload,
        records,
        slots,
        question=question,
        candidate_transaction_id=stored_transaction,
    ):
        return None, "canonical_semantic_pack_proposition_binding_mismatch"
    span_digest = qasper_canonical_span_universe_digest(records)
    if span_digest != str(payload.get("span_universe_digest") or ""):
        return None, "canonical_semantic_pack_identity_mismatch"
    integer_fields = _pack_integer_fields(payload)
    if integer_fields is None:
        return None, "canonical_semantic_pack_identity_mismatch"
    item_char_limit = integer_fields.pop("item_char_limit")
    source_records = _source_records_from_payload(payload)
    if source_records is None:
        return None, "canonical_semantic_pack_identity_mismatch"
    recomputed_pack_digest = semantic_proposition_pack_digest(
        build_question_proposition(question),
        slots,
        records,
        item_char_limit=item_char_limit,
    )
    if recomputed_pack_digest != str(payload.get("semantic_pack_digest") or ""):
        return None, "canonical_semantic_pack_identity_mismatch"
    packing = _build_loaded_packing(
        payload,
        records=records,
        source_records=source_records,
        item_char_limit=item_char_limit,
        semantic_pack_digest=recomputed_pack_digest,
        integer_fields=integer_fields,
    )
    return packing, ""


def _build_loaded_packing(
    payload: dict[str, Any],
    *,
    records: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    item_char_limit: int,
    semantic_pack_digest: str,
    integer_fields: dict[str, int],
) -> SemanticPropositionEvidencePacking:
    observation = _mapping(payload.get("source_packing_observation"))
    return SemanticPropositionEvidencePacking(
        records=records,
        source_records=deepcopy(source_records),
        item_char_limit=item_char_limit,
        input_token_budget=integer_fields["input_token_budget"],
        estimated_input_tokens=integer_fields["estimated_input_tokens"],
        dropped_count=integer_fields["dropped_count"],
        truncated_count=integer_fields["truncated_count"],
        semantic_pack_digest=semantic_pack_digest,
        question_proposition=deepcopy(payload.get("question_proposition") or {}),
        question_proposition_resolution=deepcopy(
            payload.get("question_proposition_resolution") or {}
        ),
        source_decisions=deepcopy(_mapping_list(observation.get("source_decisions"))),
        window_decisions=deepcopy(_mapping_list(observation.get("window_decisions"))),
        source_input_snapshot=deepcopy(
            _mapping(observation.get("source_input_snapshot"))
        ),
    )


def _stored_binding_reason(
    payload: dict[str, Any],
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    *,
    question: str,
    candidate_transaction_id: str,
) -> str:
    binding = candidate_evidence_set_binding(
        records,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    if payload.get("proposition_binding") != binding:
        return "canonical_semantic_pack_proposition_binding_mismatch"
    if str(payload.get("proposition_binding_digest") or "") != str(
        binding.get("binding_digest") or ""
    ):
        return "canonical_semantic_pack_proposition_binding_mismatch"
    if candidate_required_slots_from_binding(slots, binding) != slots:
        return "canonical_semantic_pack_proposition_binding_mismatch"
    return ""


def _pack_integer_fields(payload: dict[str, Any]) -> dict[str, int] | None:
    fields: dict[str, int] = {}
    for key in (
        "item_char_limit",
        "input_token_budget",
        "estimated_input_tokens",
        "dropped_count",
        "truncated_count",
    ):
        value = _nonnegative_int(payload.get(key))
        if value is None:
            return None
        fields[key] = value
    return fields


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


def qasper_canonical_evidence_plans(
    bundle: EvidenceBundle,
) -> dict[str, dict[str, Any]] | None:
    """Return the validated frozen plan choices for the QASPER verifier.

    ``None`` means this is not a frozen QASPER path.  An empty mapping is a
    deliberate fail-closed state: ambiguous and unresolved observations may be
    reviewed, but neither can be selected as semantic authority.
    """

    raw_pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw_pack, dict):
        return None
    binding = raw_pack.get("proposition_binding")
    if not isinstance(binding, dict):
        return {}
    state = str(binding.get("binding_state") or "")
    plan = binding.get("canonical_evidence_plan")
    if not isinstance(plan, dict):
        return {}
    selected_key = {
        "relation_bound_support": "support_plan",
        "relation_bound_contradiction": "contradiction_plan",
    }.get(state)
    if selected_key is None:
        return {}
    selected = plan.get(selected_key)
    if not isinstance(selected, dict):
        return {}
    plan_id = str(selected.get("plan_id") or "")
    span_refs = tuple(str(ref) for ref in selected.get("span_refs") or [] if ref)
    relation = str(selected.get("polarity_relation") or "")
    if (
        not plan_id
        or not span_refs
        or relation
        not in {
            "proposition_support",
            "explicit_contradiction",
        }
    ):
        return {}
    return {
        plan_id: {
            "plan_id": plan_id,
            "polarity_relation": relation,
            "span_refs": span_refs,
            "slot_refs": deepcopy(selected.get("slot_refs") or {}),
            "event_binding_id": str(selected.get("event_binding_id") or ""),
            "required_object_tokens": list(
                selected.get("required_object_tokens") or []
            ),
            "covered_object_tokens": list(selected.get("covered_object_tokens") or []),
            "event_subplans": deepcopy(selected.get("event_subplans") or []),
            "comparison_relation": deepcopy(selected.get("comparison_relation")),
        }
    }


def qasper_canonical_plan_construction_trace(
    bundle: EvidenceBundle,
) -> dict[str, Any] | None:
    """Return the immutable planner trace stored with a frozen QASPER pack."""

    raw_pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw_pack, dict):
        return None
    binding = raw_pack.get("proposition_binding")
    if not isinstance(binding, dict):
        return None
    trace = binding.get("plan_construction_trace")
    return deepcopy(trace) if isinstance(trace, dict) else None


def qasper_source_packing_observation(
    bundle: EvidenceBundle,
) -> dict[str, Any] | None:
    raw_pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw_pack, dict):
        return None
    observation = raw_pack.get("source_packing_observation")
    return deepcopy(observation) if isinstance(observation, dict) else None


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
