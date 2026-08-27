from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_phrase_extraction import source_page_locator
from ktem.docqa.question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    QuestionProposition,
    build_question_proposition,
    resolve_question_proposition,
)
from ktem.docqa.retrieval_semantic_identity import semantic_retrieval_identity

from .mara_qasper_candidate_evidence import evidence_polarity_priority
from .mara_semantic_candidate_priority import (
    candidate_source_fields,
    semantic_record_priority,
)
from .mara_semantic_proposition_packing_support import (
    evidence_alignment_score,
    evidence_refs,
    matching_slot_ids,
)
from .mara_semantic_proposition_packing_support import optional_int as _optional_int
from .mara_semantic_proposition_packing_support import ranked_evidence_positions
from .mara_semantic_proposition_packing_support import (
    slot_description as _slot_description,
)
from .mara_semantic_proposition_packing_support import slot_value as _slot_value
from .mara_semantic_proposition_packing_support import slot_values, stable_source_id
from .mara_semantic_proposition_span_selectors import (
    canonical_span_selectors as _canonical_span_selectors,
)

SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS = 4096
SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET = 3072
SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS = 12
SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS = 2000
SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS = 512
SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS = 16000
SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS = 640
SEMANTIC_PROPOSITION_PACK_CONTRACT = "semantic_proposition_pack.v2"


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
    item_char_limit: int
    input_token_budget: int
    estimated_input_tokens: int
    dropped_count: int
    truncated_count: int
    semantic_pack_digest: str
    question_proposition: dict[str, Any]
    question_proposition_resolution: dict[str, Any]

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
    preferred = _preferred_evidence_ids(request)
    ranked_positions = ranked_evidence_positions(bundle)
    records: list[tuple[tuple[int | float, ...], dict[str, Any]]] = []
    seen: set[str] = set()
    for index, item in enumerate(bundle.items):
        try:
            identity = identity_of(item)
        except ValueError:
            continue
        evidence_id = identity.key
        text = evidence_item_text(item)
        if not text.strip() or evidence_id in seen:
            continue
        seen.add(evidence_id)
        source_id, page_label = source_page_locator(item)
        stable_id = stable_source_id(item) or source_id or identity.source_id
        required_slot_ids = matching_slot_ids(slots, evidence_id)
        alignment_score = evidence_alignment_score(request, question, item)
        polarity_priority = evidence_polarity_priority(question, text)
        slot_priority = 0 if evidence_id in preferred or required_slot_ids else 1
        ranked_position = ranked_positions.get(
            evidence_id, len(ranked_positions) + index
        )
        priority = semantic_record_priority(
            question,
            text,
            candidate_priority=candidate_priority,
            polarity_priority=polarity_priority,
            alignment_score=alignment_score,
            slot_priority=slot_priority,
            ranked_position=ranked_position,
        )
        record = {
            "evidence_id": evidence_id,
            "semantic_identity": semantic_retrieval_identity(item) or evidence_id,
            "source_id": stable_id,
            "page_label": page_label,
            "section_id": str(item.get("section_id") or "").strip(),
            "canonical_start": _optional_int(item.get("canonical_start")),
            "evidence_refs": list(evidence_refs(item)),
            "required_slot_ids": list(required_slot_ids),
            "proposition_alignment_score": alignment_score,
            "text": text,
            **candidate_source_fields(text, enabled=candidate_priority),
        }
        records.append((priority, record))
    selected = _selected_evidence_records(records)
    item_char_limit = _evidence_item_char_limit(request)
    packed, estimated_input_tokens, truncated_count = _fit_evidence_records(
        selected,
        question=question,
        slots=slots,
        item_char_limit=item_char_limit,
    )
    resolution = resolve_question_proposition(question)
    proposition = resolution.proposition
    return SemanticPropositionEvidencePacking(
        records=packed,
        item_char_limit=item_char_limit,
        input_token_budget=SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
        estimated_input_tokens=estimated_input_tokens,
        dropped_count=len(records) - len(packed),
        truncated_count=truncated_count,
        semantic_pack_digest=semantic_proposition_pack_digest(
            proposition,
            slots,
            packed,
            item_char_limit=item_char_limit,
        ),
        question_proposition=proposition.as_dict(),
        question_proposition_resolution=resolution.as_dict(),
    )


def _selected_evidence_records(
    records: list[tuple[tuple[int | float, ...], dict[str, Any]]],
) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda row: (row[0], row[1]["evidence_id"]),
    )
    return [
        value for _priority, value in ranked[:SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS]
    ]


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
) -> tuple[list[dict[str, Any]], int, int]:
    fitted: list[dict[str, Any]] = []
    truncated_count = 0
    estimated_input_tokens = 0
    for record in records:
        source_text = record["text"]
        fair_item_limit = min(
            item_char_limit,
            max(
                SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS,
                (
                    SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET
                    * 3
                    // max(
                        1, min(len(records), SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS)
                    )
                ),
            ),
        )
        text, text_start = _relevant_evidence_window(
            source_text, question, fair_item_limit
        )
        if not text:
            continue
        candidate, candidate_input_tokens = _fitting_candidate(
            fitted,
            record,
            text,
            text_start=text_start,
            question=question,
            slots=slots,
        )
        if candidate is None:
            (
                candidate,
                candidate_input_tokens,
                text,
                text_start,
            ) = _largest_fitting_window(
                fitted,
                record,
                source_text,
                question=question,
                slots=slots,
                item_char_limit=item_char_limit,
            )
        if candidate is None:
            continue
        fitted = candidate
        estimated_input_tokens = candidate_input_tokens
        if text != source_text:
            truncated_count += 1
    return fitted, estimated_input_tokens, truncated_count


def _fitting_candidate(
    fitted: list[dict[str, Any]],
    record: dict[str, Any],
    text: str,
    *,
    text_start: int,
    question: str,
    slots: list[dict[str, str]],
) -> tuple[list[dict[str, Any]] | None, int]:
    candidate = _label_evidence_records(
        [*fitted, {**record, "text": text, "text_start": text_start}]
    )
    try:
        prompt = semantic_proposition_verifier_prompt(question, slots, candidate)
    except ValueError:
        return None, 0
    estimated_input_tokens = _estimated_message_tokens(prompt)
    if estimated_input_tokens > SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET:
        return None, 0
    return candidate, estimated_input_tokens


def _largest_fitting_window(
    fitted: list[dict[str, Any]],
    record: dict[str, Any],
    source_text: str,
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> tuple[list[dict[str, Any]] | None, int, str, int]:
    upper = min(len(source_text), item_char_limit) - 1
    if upper < SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS:
        return None, 0, "", 0
    lower = SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS
    best_candidate: list[dict[str, Any]] | None = None
    best_estimate = 0
    best_text = ""
    best_start = 0
    while lower <= upper:
        limit = (lower + upper) // 2
        text, text_start = _relevant_evidence_window(source_text, question, limit)
        candidate, estimate = _fitting_candidate(
            fitted,
            record,
            text,
            text_start=text_start,
            question=question,
            slots=slots,
        )
        if candidate is None:
            upper = limit - 1
            continue
        best_candidate = candidate
        best_estimate = estimate
        best_text = text
        best_start = text_start
        lower = limit + 1
    return best_candidate, best_estimate, best_text, best_start


def _label_evidence_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        label = f"E{index}"
        labeled.append(
            {
                **record,
                "label": label,
                "selectors": _canonical_span_selectors(
                    label,
                    str(record["text"]),
                    int(record.get("text_start") or 0),
                    _optional_int(record.get("canonical_start")),
                    selector_max_chars=SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS,
                ),
            }
        )
    return labeled


def _estimated_message_tokens(prompt: str) -> int:
    return (
        64
        + _estimated_text_tokens(SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT)
        + _estimated_text_tokens(prompt)
    )


def _estimated_text_tokens(text: str) -> int:
    byte_count = len(text.encode("utf-8"))
    lexical_piece_count = len(re.findall(r"\w+|[^\w\s]", text))
    byte_estimate = (byte_count + 2) // 3
    lexical_estimate = (lexical_piece_count * 3 + 1) // 2
    return max(byte_estimate, lexical_estimate)


def _relevant_evidence_window(text: str, question: str, limit: int) -> tuple[str, int]:
    if len(text) <= limit:
        return text, 0
    tokens = sorted(
        set(re.findall(r"\w[\w-]{3,}", question.casefold())),
        key=lambda value: (-len(value), value),
    )
    lowered = text.casefold()
    positions = [lowered.find(token) for token in tokens]
    positions = [value for value in positions if value >= 0]
    if not positions:
        return text[:limit], 0
    max_start = len(text) - limit
    starts = {max(0, min(position - (limit // 3), max_start)) for position in positions}
    start = max(
        starts,
        key=lambda value: (
            sum(token in lowered[value : value + limit] for token in tokens),
            -value,
        ),
    )
    return text[start : start + limit], start


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
            "system_prompt": SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT,
            "proposal_schema": "semantic_proposition_verdict.v4",
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


def _preferred_evidence_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return {
        str(evidence_id).strip()
        for slot in raw_slots
        for evidence_id in (
            slot.get("evidence_ids", [])
            if isinstance(slot, dict)
            else getattr(slot, "evidence_ids", ()) or ()
        )
        if str(evidence_id).strip()
    }
