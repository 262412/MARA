from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_phrase_extraction import source_page_locator

SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS = 4096
SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET = 3072
SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS = 12
SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS = 2000
SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS = 512
SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS = 16000

SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT = (
    "You are a conservative document-grounded proposition verifier. Decide the "
    "complete yes/no proposition in the question from the labeled retrieved "
    "evidence excerpts only. Return yes or no only when two to four distinct "
    "premises from one source are jointly sufficient, every selected premise is "
    "necessary, and no selected premise alone establishes the complete "
    "proposition. Otherwise return insufficient_evidence. For every premise, "
    "copy one exact contiguous quote, state the proposition fragment entailed by "
    "that quote, and bind it to the verification slots it supports. Treat actor, "
    "scope, modality, comparison direction, negation, quantifiers, and time as "
    "strict. Do not use outside knowledge. Missing mentions or incomplete "
    "retrieval never prove no; an explicit negative or contradiction is required. "
    "For questions about the authors or current study, at least one premise must "
    "explicitly anchor their action. For questions about a named subject, the "
    "premise set must explicitly anchor that subject. Conflicting evidence is "
    "insufficient. Never copy the excerpt delimiters."
)


@dataclass(frozen=True)
class SemanticPropositionEvidencePacking:
    records: list[dict[str, str]]
    item_char_limit: int
    input_token_budget: int
    estimated_input_tokens: int
    dropped_count: int
    truncated_count: int

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
    records: list[tuple[int, int, int, dict[str, str]]] = []
    seen: set[str] = set()
    for index, item in enumerate(bundle.items):
        try:
            identity = identity_of(item)
        except ValueError:
            continue
        evidence_id = identity.key
        text = evidence_item_text(item).strip()
        if not text or evidence_id in seen:
            continue
        seen.add(evidence_id)
        source_id, page_label = source_page_locator(item)
        records.append(
            (
                0 if evidence_id in preferred else 1,
                ranked_positions.get(evidence_id, len(ranked_positions) + index),
                index,
                {
                    "evidence_id": evidence_id,
                    "source_id": source_id or identity.source_id,
                    "page_label": page_label,
                    "section_id": str(item.get("section_id") or "").strip(),
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
    return SemanticPropositionEvidencePacking(
        records=packed,
        item_char_limit=item_char_limit,
        input_token_budget=SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
        estimated_input_tokens=estimated_input_tokens,
        dropped_count=len(records) - len(packed),
        truncated_count=truncated_count,
    )


def semantic_proposition_verifier_prompt(
    question: str,
    slots: list[dict[str, str]],
    packed: list[dict[str, str]],
) -> str:
    slot_text = "\n".join(
        f"- {value['slot_id']}: {value['description'] or 'complete proposition support'}"
        for value in slots
    )
    evidence_text = "\n\n".join(
        "\n".join(
            (
                f"[{value['label']}] source={value['source_id']} "
                f"page={value['page_label'] or '-'} section={value['section_id'] or '-'}",
                "<evidence>",
                value["text"],
                "</evidence>",
            )
        )
        for value in packed
    )
    prompt = (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"REQUIRED VERIFICATION SLOTS:\n{slot_text}\n\n"
        f"RETRIEVED EVIDENCE EXCERPTS:\n{evidence_text}\n\n"
        "Return exactly one JSON object. For yes or no, jointly_complete and "
        "each_premise_required must both be true and premises must contain two "
        "to four records. For insufficient_evidence, use false for both flags "
        "and an empty premises array."
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
    records: list[dict[str, str]],
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> tuple[list[dict[str, str]], int, int]:
    fitted: list[dict[str, str]] = []
    truncated_count = 0
    estimated_input_tokens = 0
    for record in records:
        source_text = record["text"]
        text = _relevant_evidence_window(source_text, question, item_char_limit)
        if not text:
            continue
        candidate, candidate_input_tokens = _fitting_candidate(
            fitted,
            record,
            text,
            question=question,
            slots=slots,
        )
        if candidate is None:
            candidate, candidate_input_tokens, text = _largest_fitting_window(
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
    fitted: list[dict[str, str]],
    record: dict[str, str],
    text: str,
    *,
    question: str,
    slots: list[dict[str, str]],
) -> tuple[list[dict[str, str]] | None, int]:
    candidate = _label_evidence_records([*fitted, {**record, "text": text}])
    try:
        prompt = semantic_proposition_verifier_prompt(question, slots, candidate)
    except ValueError:
        return None, 0
    estimated_input_tokens = _estimated_message_tokens(prompt)
    if estimated_input_tokens > SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET:
        return None, 0
    return candidate, estimated_input_tokens


def _largest_fitting_window(
    fitted: list[dict[str, str]],
    record: dict[str, str],
    source_text: str,
    *,
    question: str,
    slots: list[dict[str, str]],
    item_char_limit: int,
) -> tuple[list[dict[str, str]] | None, int, str]:
    upper = min(len(source_text), item_char_limit) - 1
    if upper < SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS:
        return None, 0, ""
    lower = SEMANTIC_PROPOSITION_VERIFIER_MIN_ITEM_CHARS
    best_candidate: list[dict[str, str]] | None = None
    best_estimate = 0
    best_text = ""
    while lower <= upper:
        limit = (lower + upper) // 2
        text = _relevant_evidence_window(source_text, question, limit)
        candidate, estimate = _fitting_candidate(
            fitted,
            record,
            text,
            question=question,
            slots=slots,
        )
        if candidate is None:
            upper = limit - 1
            continue
        best_candidate = candidate
        best_estimate = estimate
        best_text = text
        lower = limit + 1
    return best_candidate, best_estimate, best_text


def _label_evidence_records(
    records: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        {**record, "label": f"E{index}"}
        for index, record in enumerate(records, start=1)
    ]


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


def _relevant_evidence_window(text: str, question: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    tokens = sorted(
        set(re.findall(r"\w[\w-]{3,}", question.casefold())),
        key=lambda value: (-len(value), value),
    )
    lowered = text.casefold()
    positions = [lowered.find(token) for token in tokens]
    positions = [value for value in positions if value >= 0]
    if not positions:
        return text[:limit]
    max_start = len(text) - limit
    starts = {max(0, min(position - (limit // 3), max_start)) for position in positions}
    start = max(
        starts,
        key=lambda value: (
            sum(token in lowered[value : value + limit] for token in tokens),
            -value,
        ),
    )
    return text[start : start + limit]


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
