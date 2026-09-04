from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding as _candidate_evidence_set_binding,
)
from .mara_qasper_candidate_evidence import candidate_required_slots_from_binding
from .mara_qasper_candidate_evidence import (
    candidate_selector_ids as _candidate_selector_ids,
)
from .mara_qasper_candidate_evidence import (
    candidate_selector_options as _candidate_selector_options,
)
from .mara_qasper_candidate_evidence import (
    exact_candidate_slot_binding as _exact_candidate_slot_binding,
)
from .mara_qasper_candidate_identity import candidate_digest as _trace_digest
from .mara_qasper_candidate_selector_projection import (
    prioritized_candidate_prompt_evidence as _prioritized_candidate_prompt_evidence,
)
from .mara_qasper_selector_trace_projection import (
    candidate_record_occurrence_indices,
    project_qasper_canonical_selector_trace,
)
from .mara_qasper_semantic_pack import prepare_qasper_canonical_records_with_trace
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SemanticPropositionEvidencePacking,
    compact_json,
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)


def _candidate_evidence(
    request: Any,
    question: str,
    bundle: EvidenceBundle,
    *,
    candidate_transaction_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any], SemanticPropositionEvidencePacking]:
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    records = _candidate_prompt_records(packing)
    prioritized_records = _prioritized_candidate_prompt_evidence(
        records,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    (
        records,
        canonical_selector_projection_trace,
    ) = prepare_qasper_canonical_records_with_trace(
        question,
        prioritized_records,
        candidate_transaction_id=candidate_transaction_id,
    )
    canonical_record_count = len(records)
    semantic_filtered_count = len(prioritized_records) - len(records)
    (
        records,
        bound_slots,
        evidence_set_binding,
        candidate_dropped_count,
        candidate_prompt_projection_trace,
    ) = _fit_candidate_prompt_evidence(
        question,
        records,
        slots=slots,
        proposition=packing.question_proposition,
        proposition_resolution=packing.question_proposition_resolution,
        candidate_transaction_id=candidate_transaction_id,
    )
    canonical_selector_projection_trace = project_qasper_canonical_selector_trace(
        canonical_selector_projection_trace,
        source_record_count=canonical_record_count,
        selected_indices=list(
            candidate_prompt_projection_trace.get("selected_record_indices") or []
        ),
        rejection_reason="candidate_prompt_char_budget",
    )
    diagnostics = _candidate_evidence_diagnostics(
        bundle,
        packing,
        semantic_filtered_count=semantic_filtered_count,
        candidate_dropped_count=candidate_dropped_count,
        bound_slots=bound_slots,
        evidence_set_binding=evidence_set_binding,
        candidate_prompt_projection_trace=candidate_prompt_projection_trace,
        canonical_selector_projection_trace=canonical_selector_projection_trace,
    )
    return records, diagnostics, packing


def _candidate_prompt_records(
    packing: SemanticPropositionEvidencePacking,
) -> list[dict[str, Any]]:
    records = [
        {
            **deepcopy(record),
            "label": str(record["label"]),
            "evidence_id": str(record["evidence_id"]),
            "text": str(record["text"]),
            "text_start": int(record.get("text_start") or 0),
            "evidence_refs": [
                str(value).strip()
                for value in record.get("evidence_refs", [])
                if str(value).strip()
            ],
            "required_slot_ids": [
                str(value).strip()
                for value in record.get("required_slot_ids", [])
                if str(value).strip()
            ],
            "proposition_alignment_score": float(
                record.get("proposition_alignment_score") or 0.0
            ),
            "canonical_start": record.get("canonical_start"),
            "candidate_source_text": str(
                record.get("candidate_source_text") or record["text"]
            ),
            "candidate_source_text_start": int(
                record.get("candidate_source_text_start") or 0
            ),
            "selectors": list(record.get("selectors", [])),
        }
        for record in packing.records
    ]
    return records


def _candidate_evidence_diagnostics(
    bundle: EvidenceBundle,
    packing: SemanticPropositionEvidencePacking,
    *,
    semantic_filtered_count: int,
    candidate_dropped_count: int,
    bound_slots: list[dict[str, Any]],
    evidence_set_binding: dict[str, Any],
    candidate_prompt_projection_trace: dict[str, Any],
    canonical_selector_projection_trace: dict[str, Any],
) -> dict[str, Any]:
    pre_request_dropped_count = semantic_filtered_count + candidate_dropped_count
    return {
        "evidence_input_count": len(bundle.items),
        "evidence_dropped_count": packing.dropped_count + pre_request_dropped_count,
        "semantic_pack_filtered_evidence_count": semantic_filtered_count,
        "candidate_prompt_dropped_evidence_count": pre_request_dropped_count,
        "pre_request_dropped_evidence_count": pre_request_dropped_count,
        "evidence_truncated_count": packing.truncated_count,
        "evidence_estimated_input_tokens": packing.estimated_input_tokens,
        "evidence_token_budget": packing.input_token_budget,
        "evidence_pack_digest": packing.semantic_pack_digest,
        "prompt_char_limit": SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
        "typed_proposition": packing.question_proposition,
        "question_proposition_resolution": packing.question_proposition_resolution,
        "required_slots": bound_slots,
        "canonical_projection_required": True,
        "candidate_evidence_set_binding": evidence_set_binding,
        "candidate_prompt_projection_trace": candidate_prompt_projection_trace,
        "canonical_selector_projection_trace": canonical_selector_projection_trace,
    }


def _fit_candidate_prompt_evidence(
    question: str,
    records: list[dict[str, Any]],
    *,
    slots: list[dict[str, Any]],
    proposition: dict[str, Any],
    proposition_resolution: dict[str, Any],
    candidate_transaction_id: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    int,
    dict[str, Any],
]:
    selected = list(records)
    attempts: list[dict[str, Any]] = []
    canonical_projection_events: list[dict[str, Any]] = []
    dropped_for_prompt = False
    while selected:
        evidence_set_binding, bound_slots, prompt = _candidate_prompt_fit_state(
            question,
            selected,
            slots=slots,
            proposition=proposition,
            proposition_resolution=proposition_resolution,
            candidate_transaction_id=candidate_transaction_id,
        )
        attempts.append(_candidate_prompt_fit_attempt(selected, prompt, len(attempts)))
        if len(prompt) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
            if dropped_for_prompt:
                selected, projection_event = _reproject_prompt_records(
                    question,
                    selected,
                    candidate_transaction_id=candidate_transaction_id,
                )
                dropped_for_prompt = False
                if projection_event is not None:
                    canonical_projection_events.append(projection_event)
                    if not selected:
                        break
                    continue
            return (
                selected,
                bound_slots,
                evidence_set_binding,
                len(records) - len(selected),
                _prompt_projection_trace(
                    records,
                    selected,
                    attempts,
                    canonical_projection_events=canonical_projection_events,
                ),
            )
        selected.pop()
        dropped_for_prompt = True
    evidence_set_binding = _candidate_evidence_set_binding(
        [],
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    return (
        [],
        _bound_candidate_slots(slots, [], binding=evidence_set_binding),
        evidence_set_binding,
        len(records),
        _prompt_projection_trace(
            records,
            [],
            attempts,
            canonical_projection_events=canonical_projection_events,
        ),
    )


def _candidate_prompt_fit_state(
    question: str,
    selected: list[dict[str, Any]],
    *,
    slots: list[dict[str, Any]],
    proposition: dict[str, Any],
    proposition_resolution: dict[str, Any],
    candidate_transaction_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    evidence_set_binding = _candidate_evidence_set_binding(
        selected,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    bound_slots = _bound_candidate_slots(
        slots,
        selected,
        binding=evidence_set_binding,
    )
    prompt = _candidate_prompt(
        question,
        selected,
        proposition=proposition,
        proposition_resolution=proposition_resolution,
        required_slots=bound_slots,
        evidence_set_binding=evidence_set_binding,
    )
    return evidence_set_binding, bound_slots, prompt


def _candidate_prompt_fit_attempt(
    selected: list[dict[str, Any]],
    prompt: str,
    attempt_index: int,
) -> dict[str, Any]:
    return {
        "attempt": attempt_index + 1,
        "record_ids": [str(record.get("evidence_id") or "") for record in selected],
        "prompt_chars": len(prompt),
        "decision": (
            "accepted"
            if len(prompt) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS
            else "drop_last_record"
        ),
    }


def _reproject_prompt_records(
    question: str,
    selected: list[dict[str, Any]],
    *,
    candidate_transaction_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    projected, projection_trace = prepare_qasper_canonical_records_with_trace(
        question,
        selected,
        candidate_transaction_id=candidate_transaction_id,
    )
    if projected == selected:
        return selected, None
    return projected, {
        "before_record_ids": [
            str(record.get("evidence_id") or "") for record in selected
        ],
        "after_record_ids": [
            str(record.get("evidence_id") or "") for record in projected
        ],
        "before_record_digest": _trace_digest(selected),
        "after_record_digest": _trace_digest(projected),
        "projection_trace_digest": _trace_digest(projection_trace),
    }


def _prompt_projection_trace(
    records: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    canonical_projection_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_indices = candidate_record_occurrence_indices(records, selected)
    selected_index_set = set(selected_indices)
    decisions = [
        {
            "record_index": index + 1,
            "evidence_id": str(record.get("evidence_id") or ""),
            "selected": index in selected_index_set,
            "decision": (
                "selected_for_candidate_prompt"
                if index in selected_index_set
                else "candidate_prompt_char_budget"
            ),
        }
        for index, record in enumerate(records)
    ]
    canonical_projection_events = list(canonical_projection_events or [])
    return {
        "contract_id": "qasper_candidate_prompt_projection.v1",
        "complete": True,
        "input_record_count": len(records),
        "selected_record_count": len(selected),
        "decision_count": len(decisions),
        "decisions_digest": _trace_digest(decisions),
        "decisions": decisions,
        "attempt_count": len(attempts),
        "attempts_digest": _trace_digest(attempts),
        "attempts": attempts,
        "selected_record_indices": selected_indices,
        "selected_record_indices_digest": _trace_digest(selected_indices),
        "canonical_projection_event_count": len(canonical_projection_events),
        "canonical_projection_events": canonical_projection_events,
    }


def _candidate_prompt(
    question: str,
    evidence: list[dict[str, Any]],
    *,
    proposition: dict[str, Any] | None = None,
    proposition_resolution: dict[str, Any] | None = None,
    required_slots: list[dict[str, Any]] | None = None,
    evidence_set_binding: dict[str, Any] | None = None,
) -> str:
    proposition_text = compact_json(proposition or {})
    resolution_status = str((proposition_resolution or {}).get("status") or "")
    slot_text = "\n".join(
        "- "
        + str(slot.get("slot_id") or "")
        + ": "
        + str(slot.get("description") or "complete proposition support")
        for slot in required_slots or []
    )
    prompt_evidence = evidence
    evidence_text = "\n\n".join(
        "\n".join(
            [
                f"[{record['label']}]",
                "selector_options="
                + compact_json(
                    _compact_candidate_selector_options(record, question=question),
                ),
            ]
        )
        for record in prompt_evidence
    )
    evidence_set_binding = (
        evidence_set_binding
        if evidence_set_binding is not None
        else _candidate_evidence_set_binding(prompt_evidence, question)
    )
    return (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        "TYPED QUESTION PROPOSITION:\n"
        f"{proposition_text}\n"
        f"QUESTION PROPOSITION RESOLUTION STATUS: {resolution_status or 'unknown'}\n\n"
        "REQUIRED VERIFICATION SLOTS:\n"
        f"{slot_text or '- none'}\n\n"
        f"CANONICAL RELATION-BEARING SPAN SET:\n{evidence_text}\n\n"
        "CANDIDATE EVIDENCE-SET OBSERVATION:\n"
        f"{compact_json(_compact_candidate_evidence_set_binding(evidence_set_binding))}"
        "\n\n"
        "CANDIDATE DECISION RULES:\n"
        "Judge the exact typed actor-predicate-object-quantifier proposition, not "
        "keyword co-occurrence. An incompatible definition or mutually exclusive scope, "
        "quantity, or relation may be an explicit contradiction without the literal word "
        "not; missing evidence alone remains unanswerable. For inspect, analyze, or "
        "evaluate questions, an exact observation or error-analysis span may express the "
        "predicate even when it uses a more specific verb.\n\n"
        "Use only the exact selector options in this immutable span universe. "
        "Locally verified slot bindings and the set observation are structural "
        "constraints, not permission to invent evidence. A record ID or first "
        "selector is not a proposition binding. "
        "one to four exact selectors may cover applicable proposition slots by union. "
        "Support and explicit_contradiction are separate set-level observations; "
        "conflicts remain undetermined. Quantifier none is not evidence and remains "
        "not_applicable. Do not rewrite the parsed candidate; return one JSON object "
        "matching the required schema."
    )


def _compact_candidate_selector_options(
    record: dict[str, Any],
    *,
    question: str,
) -> list[dict[str, Any]]:
    """Keep exact span identity while omitting fields repeated by the record."""

    fields = (
        "evidence_ref",
        "span_start",
        "span_end",
        "text",
        "allowed_proposition_slots",
        "relation_bearing",
        "candidate_relation_role",
        "local_relation_state",
        "polarity_signal",
    )
    return [
        {
            **{field: option[field] for field in fields},
            "proposition_slot_spans": {
                slot: {
                    key: span[key]
                    for key in ("evidence_ref", "span_start", "span_end", "text")
                }
                for slot, span in dict(
                    option.get("proposition_slot_spans") or {}
                ).items()
            },
        }
        for option in _candidate_selector_options(record, question=question)
    ]


def _compact_candidate_evidence_set_binding(
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Represent set-level observations using references, not repeated span text."""

    return {
        "binding_status": binding.get("binding_status", "missing"),
        "selector_universe_status": binding.get("selector_universe_status", "bounded"),
        "polarity_signal": binding.get("polarity_signal", "undetermined"),
        "selected_refs": list(binding.get("evidence_refs") or []),
        "support_refs": list(binding.get("support_evidence_refs") or []),
        "contradiction_refs": list(
            binding.get("explicit_contradiction_evidence_refs") or []
        ),
        "slot_refs": binding.get("slot_evidence_refs") or {},
        "slot_child_refs": {
            slot: [str(span.get("evidence_ref") or "") for span in spans]
            for slot, spans in dict(binding.get("proposition_slot_spans") or {}).items()
        },
        "no_evidence_semantics": {
            key: (binding.get("no_evidence_semantics") or {}).get(key)
            for key in (
                "classification",
                "admissible_as_explicit_contradiction",
                "closed_world_inference_required",
            )
        },
    }


def _bound_candidate_slots(
    slots: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    binding: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if binding is not None:
        return candidate_required_slots_from_binding(slots, binding)
    available = {str(record.get("evidence_id") or "") for record in evidence}
    output: list[dict[str, Any]] = []
    for slot in slots:
        slot_id = str(slot.get("slot_id") or "")
        direct_ids = [
            str(value).strip()
            for value in slot.get("evidence_ids", [])
            if str(value).strip() in available
        ]
        derived_ids = [
            str(record["evidence_id"])
            for record in evidence
            if slot_id in record.get("required_slot_ids", [])
        ]
        retrieved_ids = list(dict.fromkeys([*direct_ids, *derived_ids]))
        bound_records = [
            record
            for record in evidence
            if slot_id in record.get("required_slot_ids", [])
            or str(record.get("evidence_id") or "") in retrieved_ids
        ]
        retrieved_refs = list(
            dict.fromkeys(
                ref
                for record in bound_records
                for ref in _candidate_selector_ids(record)
            )
        )
        exact_ids, exact_refs = _exact_candidate_slot_binding(
            slot,
            bound_records,
        )
        output.append(
            {
                "slot_id": slot_id,
                "description": str(slot.get("description") or ""),
                # Only explicit, span-level proposition binding may populate
                # these authority-shaped fields. Retrieval IDs and selector
                # options are retained separately so they cannot masquerade as
                # a verified slot binding.
                "evidence_ids": exact_ids,
                "evidence_refs": exact_refs,
                "retrieved_evidence_ids": retrieved_ids,
                "retrieved_evidence_refs": retrieved_refs,
                "binding_status": "bound" if exact_ids and exact_refs else "missing",
                "binding_reason": (
                    "exact_span_set"
                    if exact_ids and exact_refs
                    else "record_identity_only"
                    if retrieved_ids or retrieved_refs
                    else "no_retrieved_evidence"
                ),
            }
        )
    return output
