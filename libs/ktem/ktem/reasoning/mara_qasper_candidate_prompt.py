from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding as _candidate_evidence_set_binding,
)
from .mara_qasper_candidate_evidence import (
    candidate_selector_ids as _candidate_selector_ids,
)
from .mara_qasper_candidate_evidence import (
    candidate_selector_options as _candidate_selector_options,
)
from .mara_qasper_candidate_evidence import (
    exact_candidate_slot_binding as _exact_candidate_slot_binding,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
    compact_json,
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from .mara_semantic_proposition_span_selectors import canonical_span_selectors

_CANDIDATE_SELECTORS_PER_RECORD = 4


def _candidate_evidence(
    request: Any,
    question: str,
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    records = [
        {
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
    records, bound_slots, candidate_dropped_count = _fit_candidate_prompt_evidence(
        question,
        records,
        slots=slots,
        proposition=packing.question_proposition,
        proposition_resolution=packing.question_proposition_resolution,
    )
    return records, {
        "evidence_input_count": len(bundle.items),
        "evidence_dropped_count": packing.dropped_count + candidate_dropped_count,
        "candidate_prompt_dropped_evidence_count": candidate_dropped_count,
        "evidence_truncated_count": packing.truncated_count,
        "evidence_estimated_input_tokens": packing.estimated_input_tokens,
        "evidence_token_budget": packing.input_token_budget,
        "evidence_pack_digest": packing.semantic_pack_digest,
        "prompt_char_limit": SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
        "typed_proposition": packing.question_proposition,
        "question_proposition_resolution": packing.question_proposition_resolution,
        "required_slots": bound_slots,
    }


def _fit_candidate_prompt_evidence(
    question: str,
    records: list[dict[str, Any]],
    *,
    slots: list[dict[str, Any]],
    proposition: dict[str, Any],
    proposition_resolution: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    selected = list(records)
    while selected:
        bound_slots = _bound_candidate_slots(slots, selected)
        prompt = _candidate_prompt(
            question,
            selected,
            proposition=proposition,
            proposition_resolution=proposition_resolution,
            required_slots=bound_slots,
        )
        if len(prompt) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
            return selected, bound_slots, len(records) - len(selected)
        selected.pop()
    return [], _bound_candidate_slots(slots, []), len(records)


def _candidate_prompt(
    question: str,
    evidence: list[dict[str, Any]],
    *,
    proposition: dict[str, Any] | None = None,
    proposition_resolution: dict[str, Any] | None = None,
    required_slots: list[dict[str, Any]] | None = None,
) -> str:
    proposition_text = compact_json(proposition or {})
    resolution_status = str((proposition_resolution or {}).get("status") or "")
    slot_text = "\n".join(
        "- "
        + str(slot.get("slot_id") or "")
        + ": "
        + str(slot.get("description") or "complete proposition support")
        + "; binding_status="
        + str(slot.get("binding_status") or "missing")
        + "; retrieved_evidence_ids="
        + compact_json(
            slot.get("retrieved_evidence_ids", slot.get("evidence_ids", [])),
        )
        + "; retrieved_evidence_refs="
        + compact_json(
            slot.get("retrieved_evidence_refs", slot.get("evidence_refs", [])),
        )
        for slot in required_slots or []
    )
    prompt_evidence = _prioritized_candidate_prompt_evidence(evidence, question)
    evidence_text = "\n\n".join(
        "\n".join(
            [
                f"[{record['label']}] evidence_id={record['evidence_id']}",
                "selector_options="
                + compact_json(
                    _compact_candidate_selector_options(record, question=question),
                ),
            ]
        )
        for record in prompt_evidence
    )
    evidence_set_binding = _candidate_evidence_set_binding(prompt_evidence, question)
    return (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        "TYPED QUESTION PROPOSITION:\n"
        f"{proposition_text}\n"
        f"QUESTION PROPOSITION RESOLUTION STATUS: {resolution_status or 'unknown'}\n\n"
        "REQUIRED VERIFICATION SLOTS:\n"
        f"{slot_text or '- none'}\n\n"
        f"CANONICAL RETRIEVED EVIDENCE:\n{evidence_text}\n\n"
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
        "Use exact selector options; an evidence ID or a first selector is not a "
        "proposition binding. Hints and the set observation are retrieval-only. "
        "one to four exact selectors may cover applicable proposition slots by union. "
        "Support and explicit_contradiction are separate set-level observations; "
        "conflicts remain undetermined. Quantifier none is not evidence and remains "
        "not_applicable. Do not rewrite the parsed candidate; return one JSON object "
        "matching the required schema."
    )


def _prioritized_candidate_prompt_evidence(
    evidence: list[dict[str, Any]],
    question: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in evidence:
        source_text = str(
            record.get("candidate_source_text") or record.get("text") or ""
        )
        text_start = int(record.get("candidate_source_text_start") or 0)
        canonical_start = record.get("canonical_start")
        canonical_start = canonical_start if isinstance(canonical_start, int) else None
        projected = {
            **record,
            "text": source_text,
            "text_start": text_start,
            "selectors": canonical_span_selectors(
                str(record.get("label") or ""),
                source_text,
                text_start,
                canonical_start,
                selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
            ),
        }
        options = _candidate_selector_options(projected, question=question)[
            :_CANDIDATE_SELECTORS_PER_RECORD
        ]
        projected["selectors"] = [
            {
                "selector_id": option["evidence_ref"],
                "text": option["text"],
                "span_start": option["span_start"],
                "span_end": option["span_end"],
            }
            for option in options
        ]
        output.append(projected)
    return output


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
        "slot_hints",
        "polarity_signal",
    )
    return [
        {field: option[field] for field in fields}
        for option in _candidate_selector_options(record, question=question)
    ]


def _compact_candidate_evidence_set_binding(
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Represent set-level observations using references, not repeated span text."""

    return {
        "binding_status": binding.get("binding_status", "missing"),
        "polarity_signal": binding.get("polarity_signal", "undetermined"),
        "selected_refs": list(binding.get("evidence_refs") or []),
        "support_refs": list(binding.get("support_evidence_refs") or []),
        "contradiction_refs": list(
            binding.get("explicit_contradiction_evidence_refs") or []
        ),
        "slot_refs": binding.get("slot_evidence_refs") or {},
    }


def _bound_candidate_slots(
    slots: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
