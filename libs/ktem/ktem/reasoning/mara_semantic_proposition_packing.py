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
    QuestionProposition,
    build_question_proposition,
    resolve_question_proposition,
)
from ktem.docqa.retrieval_semantic_identity import semantic_retrieval_identity

SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS = 4096
SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET = 3072
SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS = 12
SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS = 2000
SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS = 512
SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS = 16000
SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS = 640
SEMANTIC_PROPOSITION_PACK_CONTRACT = "semantic_proposition_pack.v1"

SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT = (
    "You are a conservative document-grounded proposition verifier. Decide the "
    "typed question proposition from the labeled retrieved evidence spans only. "
    "Use atomic_semantic when one selected premise establishes the complete "
    "conclusion. Use composite_conjunction only when two to four genuinely "
    "conjunctive premises are jointly sufficient and every premise is necessary. "
    "Otherwise return insufficient_evidence. For every premise, select one "
    "canonical span_selector, prefer a proposition fragment that is an exact "
    "normalized substring of that span, state nothing broader than the selected "
    "text, and bind it to the verification slots it supports. For questions "
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
    "insufficient."
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
) -> SemanticPropositionEvidencePacking:
    preferred = _preferred_evidence_ids(request)
    ranked_positions = _ranked_evidence_positions(bundle)
    records: list[tuple[int, int, int, dict[str, Any]]] = []
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
        stable_source_id = _stable_source_id(item) or source_id or identity.source_id
        records.append(
            (
                0 if evidence_id in preferred else 1,
                ranked_positions.get(evidence_id, len(ranked_positions) + index),
                index,
                {
                    "evidence_id": evidence_id,
                    "semantic_identity": semantic_retrieval_identity(item)
                    or evidence_id,
                    "source_id": stable_source_id,
                    "page_label": page_label,
                    "section_id": str(item.get("section_id") or "").strip(),
                    "canonical_start": _optional_int(item.get("canonical_start")),
                    "text": text,
                },
            )
        )
    selected = [value for _priority, _rank, _index, value in sorted(records)][
        :SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS
    ]
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


def required_semantic_proposition_slots(request: Any) -> list[dict[str, str]]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    slots: list[dict[str, str]] = []
    for slot in raw_slots:
        required = (
            slot.get("required_for_verification", False)
            if isinstance(slot, dict)
            else getattr(slot, "required_for_verification", False)
        )
        slot_id = _slot_value(slot, "slot_id")
        if required and slot_id:
            slots.append({"slot_id": slot_id, "description": _slot_description(slot)})
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
) -> str:
    proposition = build_question_proposition(question)
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
    prompt = (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        "TYPED QUESTION PROPOSITION:\n"
        f"{json.dumps(proposition.as_dict(), ensure_ascii=False, separators=(',', ':'))}\n\n"
        f"REQUIRED VERIFICATION SLOTS:\n{slot_text}\n\n"
        f"CANONICAL EVIDENCE SPANS:\n{evidence_text}\n\n"
        "Return exactly one JSON object. For yes or no, choose proof_mode "
        "atomic_semantic with exactly one premise or composite_conjunction with "
        "two to four genuinely conjunctive premises. jointly_complete and "
        "each_premise_required must be true. For insufficient_evidence, use "
        "proof_mode none, false for both flags, and an empty premises array."
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
            "proposal_schema": "semantic_proposition_verdict.v3",
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
                "selectors": value["selectors"],
            }
            for value in packed
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_span_selectors(
    evidence_label: str,
    text: str,
    text_start: int,
    canonical_start: int | None,
) -> list[dict[str, Any]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r".+?(?:[.!?](?=\s|$)|\n+|$)", text, re.DOTALL):
        start, end = _trimmed_span(text, match.start(), match.end())
        if start < end:
            spans.extend(_bounded_spans(text, start, end))
        cursor = match.end()
    if cursor < len(text):
        start, end = _trimmed_span(text, cursor, len(text))
        spans.extend(_bounded_spans(text, start, end))
    return [
        {
            "selector_id": f"{evidence_label}:S{index}",
            "text": text[start:end],
            "span_start": text_start + start,
            "span_end": text_start + end,
            "canonical_start": (
                canonical_start + text_start + start
                if canonical_start is not None
                else None
            ),
            "canonical_end": (
                canonical_start + text_start + end
                if canonical_start is not None
                else None
            ),
        }
        for index, (start, end) in enumerate(spans, start=1)
    ]


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _bounded_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    output: list[tuple[int, int]] = []
    while end - start > SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS:
        limit = start + SEMANTIC_PROPOSITION_SELECTOR_MAX_CHARS
        boundary = text.rfind(" ", start, limit + 1)
        split = boundary if boundary > start else limit
        chunk_start, chunk_end = _trimmed_span(text, start, split)
        if chunk_start < chunk_end:
            output.append((chunk_start, chunk_end))
        start = split + (1 if split < end and text[split].isspace() else 0)
        start, _ = _trimmed_span(text, start, end)
    start, end = _trimmed_span(text, start, end)
    if start < end:
        output.append((start, end))
    return output


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


def _ranked_evidence_positions(bundle: EvidenceBundle) -> dict[str, int]:
    values = bundle.metadata.get("candidate_ranked_evidence") or []
    return {
        evidence_id: index
        for index, value in enumerate(values)
        if isinstance(value, dict)
        and (evidence_id := str(value.get("canonical_id") or "").strip())
    }


def _slot_value(slot: Any, key: str) -> str:
    value = slot.get(key) if isinstance(slot, dict) else getattr(slot, key, "")
    return str(value or "").strip()


def _slot_description(slot: Any) -> str:
    fields = [
        (key, _slot_value(slot, key))
        for key in ("role", "entity", "metric", "period", "statement_kind", "query")
    ]
    return "; ".join(f"{key}={value}" for key, value in fields if value)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _stable_source_id(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    for key in (
        "evaluation_source_id",
        "canonical_document_id",
        "canonical_dataset_id",
        "document_id",
    ):
        for container in (item, metadata):
            value = str(container.get(key) or "").strip()
            if value:
                return value
    return ""
