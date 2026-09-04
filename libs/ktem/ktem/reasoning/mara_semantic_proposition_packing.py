from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    QuestionProposition,
    build_question_proposition,
    resolve_question_proposition,
)

from .mara_semantic_proposition_packing_labels import (
    label_evidence_records as _label_evidence_records,
)
from .mara_semantic_proposition_packing_records import (
    dropped_source_record_count,
    ranked_source_records_with_trace,
    selected_source_records,
    source_record_decisions,
    source_record_observations,
)
from .mara_semantic_proposition_packing_support import (
    FittingWindowResult as _FittingWindowResult,
)
from .mara_semantic_proposition_packing_support import (
    estimated_text_tokens as _estimated_text_tokens,
)
from .mara_semantic_proposition_packing_support import (
    slot_description as _slot_description,
)
from .mara_semantic_proposition_packing_support import slot_value as _slot_value
from .mara_semantic_proposition_packing_support import slot_values
from .mara_semantic_proposition_source_snapshot import source_input_snapshot
from .mara_semantic_proposition_windowing import (
    relevant_evidence_window,
    windowed_evidence_records_with_trace,
)

SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS = 4096
SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET = 3072
SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS = 12
SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS = 2000
SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS = 512
SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS = 16000
SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS = 640
SEMANTIC_PROPOSITION_MAX_SELECTORS_PER_RECORD = 4
SEMANTIC_PROPOSITION_MAX_WINDOWS_PER_RECORD = 2
SEMANTIC_PROPOSITION_PACK_CONTRACT = "semantic_proposition_pack.v3"


def compact_json(value: Any) -> str:
    """Serialize prompt metadata deterministically without formatting padding."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT = (
    "You are a conservative document-grounded verifier. Judge the original "
    "structured candidate against the typed question proposition and the labeled "
    "retrieved evidence spans only. You must not independently choose, rewrite, "
    "or replace the answer candidate. Return candidate_judgment as supported, "
    "contradicted, or unknown; it is a relationship to the supplied candidate, "
    "not a new yes/no answer. "
    "Use atomic_semantic when one selected premise establishes the complete "
    "conclusion. Use composite_conjunction only when two to four genuinely "
    "conjunctive premises are jointly sufficient and every premise is necessary. "
    "Otherwise return candidate_judgment=unknown. For every premise, select one "
    "canonical span_selector, prefer a proposition fragment that is an exact "
    "normalized substring of that span, state nothing broader than the selected "
    "text, bind it to the verification slots it supports, and identify which of "
    "actor, predicate, object, and quantifier it establishes. All four proposition "
    "slots must be covered by the same selected evidence set. For original "
    "candidates yes or no, do not emit evidence_relation: it is a deterministic "
    "local projection from the original candidate and candidate_judgment; runtime "
    "injects the result onto each normalized premise after parsing. For the "
    "unanswerable candidate, follow its candidate-specific schema: unknown has "
    "no direction field, while contradicted must emit the direction required by "
    "that schema. Keyword overlap "
    "alone is never a proposition binding. For questions "
    "about inspecting, analyzing, or evaluating a system, a genuine conjunction "
    "may combine one premise that establishes the authors performed the analysis "
    "with another that establishes the exact behavior or relationship observed; "
    "the question verb need not be repeated verbatim. Treat actor, "
    "scope, modality, comparison direction, negation, quantifiers, and time as "
    "strict. Do not use outside knowledge. Missing mentions or incomplete "
    "retrieval never prove no; an explicit negative or contradiction is required. "
    "For questions about the authors or current study, at least one premise must "
    "explicitly anchor their action. For questions about a named subject, the "
    "premise set must explicitly anchor that subject. Conflicting evidence is "
    "insufficient. For candidate_judgment=unknown, identify non-empty reviewed spans, "
    "the unresolved proposition slots, and separate support and contradiction gaps."
)


@dataclass(frozen=True)
class SemanticPropositionEvidencePacking:
    records: list[dict[str, Any]]
    source_records: list[dict[str, Any]]
    item_char_limit: int
    input_token_budget: int
    estimated_input_tokens: int
    dropped_count: int
    truncated_count: int
    semantic_pack_digest: str
    question_proposition: dict[str, Any]
    question_proposition_resolution: dict[str, Any]
    source_decisions: list[dict[str, Any]] = field(default_factory=list)
    window_decisions: list[dict[str, Any]] = field(default_factory=list)
    source_input_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def packed_chars(self) -> int:
        return sum(len(value["text"]) for value in self.records)


def pack_semantic_proposition_evidence(
    request: Any,
    question: str,
    slots: list[dict[str, str]],
    bundle: EvidenceBundle,
    *,
    candidate_priority: bool = False,
) -> SemanticPropositionEvidencePacking:
    records, raw_source_decisions = ranked_source_records_with_trace(
        request,
        question,
        slots,
        bundle,
        candidate_priority=candidate_priority,
    )
    selected = selected_source_records(
        records,
        max_items=SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS,
    )
    item_char_limit = _evidence_item_char_limit(request)
    (
        packed,
        estimated_input_tokens,
        truncated_count,
        window_decisions,
    ) = _fit_evidence_records(
        selected,
        question=question,
        slots=slots,
        item_char_limit=item_char_limit,
    )
    source_observations = source_record_observations(records, selected, packed)
    source_decisions = source_record_decisions(
        raw_source_decisions,
        source_observations,
    )
    resolution = resolve_question_proposition(question)
    proposition = resolution.proposition
    return SemanticPropositionEvidencePacking(
        records=packed,
        source_records=source_observations,
        item_char_limit=item_char_limit,
        input_token_budget=SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
        estimated_input_tokens=estimated_input_tokens,
        dropped_count=dropped_source_record_count(
            [value for _priority, value in records],
            packed,
        ),
        truncated_count=truncated_count,
        semantic_pack_digest=semantic_proposition_pack_digest(
            proposition,
            slots,
            packed,
            item_char_limit=item_char_limit,
        ),
        question_proposition=proposition.as_dict(),
        question_proposition_resolution=resolution.as_dict(),
        source_decisions=source_decisions,
        source_input_snapshot=source_input_snapshot(
            request,
            question,
            slots,
            bundle,
            raw_source_decisions,
            candidate_priority=candidate_priority,
            item_char_limit=item_char_limit,
        ),
        window_decisions=window_decisions,
    )


def required_semantic_proposition_slots(request: Any) -> list[dict[str, Any]]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    slots: list[dict[str, Any]] = []
    for slot in raw_slots:
        required = (
            slot.get("required_for_verification", False)
            if isinstance(slot, dict)
            else getattr(slot, "required_for_verification", False)
        )
        slot_id = _slot_value(slot, "slot_id")
        if required and slot_id:
            slots.append(
                {
                    "slot_id": slot_id,
                    "description": _slot_description(slot),
                    "evidence_ids": list(slot_values(slot, "evidence_ids")),
                    "evidence_refs": list(slot_values(slot, "evidence_refs")),
                }
            )
    return slots


def semantic_pack_digest_for_bundle(
    request: Any,
    question: str,
    bundle: EvidenceBundle,
) -> str:
    return pack_semantic_proposition_evidence(
        request,
        question,
        required_semantic_proposition_slots(request),
        bundle,
    ).semantic_pack_digest


def semantic_proposition_verifier_prompt(
    question: str,
    slots: list[dict[str, str]],
    packed: list[dict[str, Any]],
    *,
    candidate: str = "",
) -> str:
    proposition = build_question_proposition(question)
    applicable_proposition_slots = [
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if not (slot == "quantifier" and proposition.quantifier == "none")
    ]
    not_applicable_proposition_slots = [
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if slot not in applicable_proposition_slots
    ]
    slot_text = "\n".join(
        f"- {value['slot_id']}: {value['description'] or 'complete proposition support'}"
        for value in slots
    )
    evidence_text = "\n\n".join(
        "\n".join(
            [
                f"[{value['label']}] source={value['source_id']} "
                f"page={value['page_label'] or '-'} section={value['section_id'] or '-'}",
                *[
                    f"[{selector['selector_id']}] {selector['text']}"
                    for selector in value["selectors"]
                ],
            ]
        )
        for value in packed
    )
    normalized_candidate = str(candidate or "").strip().casefold()
    direction_instruction = (
        "For the unanswerable candidate, use candidate_judgment=unknown when "
        "neither polarity is established. If candidate_judgment=contradicted, "
        "include evidence_relation only to identify whether the evidence "
        "supports or explicitly contradicts the typed proposition; runtime "
        "still validates that direction and projects the legacy polarity."
        if normalized_candidate == "unanswerable"
        else "For yes/no candidates, emit only candidate_judgment; runtime "
        "projects evidence_relation and the legacy polarity deterministically."
    )
    prompt = (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"STRUCTURED CANDIDATE TO VERIFY:\n{candidate}\n\n"
        "TYPED QUESTION PROPOSITION:\n"
        f"{json.dumps(proposition.as_dict(), ensure_ascii=False, separators=(',', ':'))}\n\n"
        f"REQUIRED VERIFICATION SLOTS:\n{slot_text}\n\n"
        f"CANONICAL EVIDENCE SPANS:\n{evidence_text}\n\n"
        "Do not answer the question independently and do not propose a replacement "
        "candidate. Return candidate_judgment=supported, contradicted, or unknown "
        f"for the exact original candidate above. {direction_instruction} "
        "Never emit a yes/no answer field. "
        "For every supported/contradicted premise, binds_proposition_slots must "
        "declare only the "
        "actor/predicate/object/quantifier fields actually established by its quote; "
        "their union must cover every applicable field within this one evidence set. "
        "Include not_applicable_proposition_slots explicitly for proposition-level "
        f"N/A fields ({json.dumps(not_applicable_proposition_slots)}); never bind "
        "an N/A field as evidence, and ensure evidence bindings cover every "
        f"applicable field ({json.dumps(applicable_proposition_slots)}). "
        "Return exactly one JSON object. For candidate_judgment=supported or "
        "candidate_judgment=contradicted, return one to four premises. The runtime "
        "derives atomic_semantic from one premise and composite_conjunction from "
        "two to four premises; do not emit proof_mode. jointly_complete and "
        "each_premise_required must be true. For candidate_judgment=unknown, use "
        "false for both flags, an empty premises array, and a "
        "non-empty unknown_assessment that states why neither support nor explicit "
        "contradiction is established."
    )
    if len(prompt) > SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
        raise ValueError("Semantic proposition verifier prompt exceeded its bound.")
    return prompt


def _evidence_item_char_limit(request: Any) -> int:
    requested = getattr(request, "max_context_length", None)
    if isinstance(requested, int) and requested > 0:
        return min(requested, SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS)
    return SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS


def _fit_evidence_records(
    records: list[dict[str, Any]],
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]]]:
    fitted: list[dict[str, Any]] = []
    source_lengths = {
        str(record.get("evidence_id") or ""): len(str(record.get("text") or ""))
        for record in records
    }
    truncated_source_ids: set[str] = set()
    estimated_input_tokens = 0
    fair_item_limit = _fair_item_char_limit(item_char_limit, len(records))
    windowed_records, window_selection_decisions = windowed_evidence_records_with_trace(
        records,
        question,
        item_char_limit=fair_item_limit,
        max_windows=SEMANTIC_PROPOSITION_MAX_WINDOWS_PER_RECORD,
        selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
    )
    window_fit_decisions: list[dict[str, Any]] = []
    for window_record in windowed_records:
        (
            candidate,
            candidate_input_tokens,
            text,
            text_start,
            decision,
        ) = _fit_window_record(
            fitted,
            window_record,
            question=question,
            slots=slots,
            item_char_limit=item_char_limit,
        )
        window_fit_decisions.append(decision)
        if candidate is None:
            continue
        fitted = candidate
        estimated_input_tokens = candidate_input_tokens
        evidence_id = str(window_record.get("evidence_id") or "")
        if text_start > 0 or len(text) < source_lengths.get(evidence_id, len(text)):
            truncated_source_ids.add(evidence_id)
    selection_trace = [
        {"stage": "window_selection", **decision}
        for decision in window_selection_decisions
    ]
    return (
        fitted,
        estimated_input_tokens,
        len(truncated_source_ids),
        [*selection_trace, *window_fit_decisions],
    )


def _fit_window_record(
    fitted: list[dict[str, Any]],
    window_record: dict[str, Any],
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> tuple[list[dict[str, Any]] | None, int, str, int, dict[str, Any]]:
    text = str(window_record["text"] or "")
    text_start = int(window_record.get("text_start") or 0)
    candidate, candidate_input_tokens, primary_reason = _fitting_candidate(
        fitted,
        window_record,
        text,
        text_start=text_start,
        question=question,
        slots=slots,
    )
    fallback_attempts: list[dict[str, Any]] = []
    if candidate is None:
        (
            candidate,
            candidate_input_tokens,
            text,
            text_start,
            fallback_attempts,
        ) = _largest_fitting_window(
            fitted,
            window_record,
            str(window_record.get("candidate_source_text") or text),
            question=question,
            slots=slots,
            item_char_limit=item_char_limit,
        )
    selected = candidate is not None
    decision = {
        "stage": "fit_to_input_budget",
        "evidence_id": str(window_record.get("evidence_id") or ""),
        "window_index": window_record.get("window_index"),
        "window_start": int(window_record.get("text_start") or 0),
        "window_end": int(window_record.get("text_start") or 0)
        + len(str(window_record.get("text") or "")),
        "window_text_digest": hashlib.sha256(
            str(window_record.get("text") or "").encode("utf-8")
        ).hexdigest(),
        "selected": selected,
        "decision": "packed" if selected else "rejected",
        "reason": (
            "accepted_with_fallback_window"
            if selected and fallback_attempts
            else "accepted_with_primary_window"
            if selected
            else "no_window_fits_input_budget"
        ),
        "primary_attempt_reason": primary_reason,
        "estimated_input_tokens": candidate_input_tokens,
        "fallback_attempts": fallback_attempts,
    }
    return candidate, candidate_input_tokens, text, text_start, decision


def _fair_item_char_limit(item_char_limit: int, record_count: int) -> int:
    fair_share = (
        SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET
        * 3
        // max(1, min(record_count, SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS))
    )
    return min(
        item_char_limit,
        max(SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS, fair_share),
    )


def _fitting_candidate(
    fitted: list[dict[str, Any]],
    record: dict[str, Any],
    text: str,
    *,
    text_start: int,
    question: str,
    slots: list[dict[str, str]],
) -> tuple[list[dict[str, Any]] | None, int, str]:
    candidate = _label_evidence_records(
        [*fitted, {**record, "text": text, "text_start": text_start}],
        question=question,
        selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
        max_selectors=SEMANTIC_PROPOSITION_MAX_SELECTORS_PER_RECORD,
    )
    try:
        prompt = semantic_proposition_verifier_prompt(question, slots, candidate)
    except ValueError:
        return None, 0, "verifier_prompt_contract_rejected"
    estimated_input_tokens = _estimated_message_tokens(prompt)
    if estimated_input_tokens > SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET:
        return None, estimated_input_tokens, "verifier_input_token_budget"
    return candidate, estimated_input_tokens, "accepted"


def _largest_fitting_window(
    fitted: list[dict[str, Any]],
    record: dict[str, Any],
    source_text: str,
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> _FittingWindowResult:
    upper = min(len(source_text), item_char_limit) - 1
    if upper < SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS:
        return None, 0, "", 0, []
    lower = SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS
    best_candidate: list[dict[str, Any]] | None = None
    best_estimate = 0
    best_text = ""
    best_start = 0
    attempts: list[dict[str, Any]] = []
    while lower <= upper:
        limit = (lower + upper) // 2
        text, text_start = relevant_evidence_window(
            source_text,
            question,
            limit,
            selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
        )
        candidate, estimate, reason = _fitting_candidate(
            fitted,
            record,
            text,
            text_start=text_start,
            question=question,
            slots=slots,
        )
        attempts.append(
            {
                "limit": limit,
                "window_start": text_start,
                "window_end": text_start + len(text),
                "window_text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "decision": "accepted" if candidate is not None else "rejected",
                "reason": reason,
                "estimated_input_tokens": estimate,
            }
        )
        if candidate is None:
            upper = limit - 1
            continue
        best_candidate = candidate
        best_estimate = estimate
        best_text = text
        best_start = text_start
        lower = limit + 1
    return best_candidate, best_estimate, best_text, best_start, attempts


def _estimated_message_tokens(prompt: str) -> int:
    return (
        64
        + _estimated_text_tokens(SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT)
        + _estimated_text_tokens(prompt)
    )


def semantic_proposition_pack_digest(
    proposition: QuestionProposition,
    slots: list[dict[str, str]],
    packed: list[dict[str, Any]],
    *,
    item_char_limit: int,
) -> str:
    payload = {
        "contract_id": SEMANTIC_PROPOSITION_PACK_CONTRACT,
        "question_proposition": proposition.as_dict(),
        "slots": slots,
        "packing": {
            "max_items": SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS,
            "item_chars": SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS,
            "effective_item_char_limit": item_char_limit,
            "input_token_budget": SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
            "max_prompt_chars": SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
            "selector_max_chars": SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
            "identity_scope": "typed_proposition_slots_and_exact_span_universe",
        },
        "evidence": [
            {
                "label": value["label"],
                "semantic_identity": value["semantic_identity"],
                "source_id": value["source_id"],
                "page_label": value.get("page_label"),
                "section_id": value.get("section_id"),
                "canonical_start": value.get("canonical_start"),
                "text_start": value.get("text_start"),
                "evidence_refs": value.get("evidence_refs", []),
                "required_slot_ids": value.get("required_slot_ids", []),
                "proposition_alignment_score": value.get(
                    "proposition_alignment_score", 0.0
                ),
                "selectors": value["selectors"],
            }
            for value in packed
        ],
    }
    canonical = compact_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
