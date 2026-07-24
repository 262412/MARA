from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from .mara_ragtruth_support import (
    claim_support_conflict,
    lexical_claim_supported,
    passage_novelty_indices,
    source_support_units,
    structured_claim_supported,
    structured_mismatch_indices,
)

RAGTRUTH_CLAIM_SYSTEM_PROMPT = (
    "You are a source-grounded claim verifier. Decide which numbered response "
    "claims are not fully supported by the source. Every entity, relation, "
    "amount, time, qualifier, and polarity must be supported. Similar words or "
    "the same topic are not enough: offered versus accepted, possible versus "
    "actual, and an item being mentioned versus having a claimed property are "
    "different facts. Plausibility is not source support. Return only the "
    "indices of unsupported claims."
)

_BLOCK_PAIRS = (
    ("Below are related passages:\n", "Below is an answer:\n"),
    ("Below is the original source:\n", "Below is a summary or response:\n"),
    ("Below is the structured JSON data:\n", "Below is an overview of the data:\n"),
)
_OUTPUT_MARKER = '\n\nReturn exactly one JSON object with the key "hallucination list".'
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[\"']?[A-Z0-9])")
_LIST_BOUNDARY_RE = re.compile(r"\n(?=\s*(?:[-*]|\d+[.)])\s+)")
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_SUPPORT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def ragtruth_task_blocks(prompt: str) -> tuple[str, str] | None:
    text = str(prompt or "")
    for source_marker, response_marker in _BLOCK_PAIRS:
        if source_marker not in text or response_marker not in text:
            continue
        source_tail = text.split(source_marker, 1)[1]
        source, response_tail = source_tail.split(response_marker, 1)
        response = response_tail.split(_OUTPUT_MARKER, 1)[0]
        return source.strip(), response.strip()
    return None


def ragtruth_task_type(prompt: str) -> str:
    text = str(prompt or "")
    if _BLOCK_PAIRS[2][0] in text:
        return "data2txt"
    if _BLOCK_PAIRS[0][0] in text:
        return "qa"
    if _BLOCK_PAIRS[1][0] in text:
        return "summary"
    return "unknown"


def response_claims(response: str) -> list[str]:
    claims: list[str] = []
    for paragraph in re.split(r"\n\s*\n", str(response or "")):
        for list_item in _LIST_BOUNDARY_RE.split(paragraph):
            list_item = _LIST_PREFIX_RE.sub("", list_item)
            for sentence in _SENTENCE_BOUNDARY_RE.split(list_item):
                value = sentence.strip()
                if value:
                    claims.append(value)
    return claims


def claim_verifier_prompt(source: str, claims: list[str]) -> str:
    numbered = "\n".join(f"[{index}] {claim}" for index, claim in enumerate(claims))
    example = ", ".join(f'"{index}":"supported"' for index in range(len(claims)))
    return (
        "/no_think\n"
        "Compare every response claim with the complete source. You must give "
        'each numbered claim exactly one verdict: "supported" only when the '
        'complete fact is entailed, otherwise "unsupported".\n\n'
        f"SOURCE:\n{source}\n\n"
        f"NUMBERED RESPONSE CLAIMS:\n{numbered}\n\n"
        f"Return one JSON object with every index present, for example: "
        f"{{{example}}}."
    )


def claim_verifier_response_format(claim_count: int) -> dict[str, Any]:
    properties = {
        str(index): {
            "type": "string",
            "enum": ["supported", "unsupported"],
        }
        for index in range(claim_count)
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ragtruth_claim_verdicts",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def unsupported_claim_indices(answer: str, claim_count: int) -> set[int]:
    try:
        parsed = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, dict):
        return set()
    return {
        index for index in range(claim_count) if parsed.get(str(index)) == "unsupported"
    }


def candidate_claim_indices(answer: str, claims: list[str]) -> set[int]:
    spans = candidate_spans(answer)
    selected: set[int] = set()
    for span in spans:
        normalized_span = _normalized_words(span)
        contained = [
            index
            for index, claim in enumerate(claims)
            if _normalized_words(claim) in normalized_span
            or normalized_span in _normalized_words(claim)
        ]
        if contained:
            selected.update(contained)
            continue
        similarities = [
            SequenceMatcher(
                None,
                normalized_span,
                _normalized_words(claim),
            ).ratio()
            for claim in claims
        ]
        if similarities and max(similarities) >= 0.45:
            selected.add(max(range(len(similarities)), key=similarities.__getitem__))
    return selected


def candidate_spans(answer: str) -> list[str]:
    try:
        parsed = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return []
    spans = parsed.get("hallucination list") if isinstance(parsed, dict) else None
    if not isinstance(spans, list):
        return []
    return [
        value.strip() for value in spans if isinstance(value, str) and value.strip()
    ]


def heuristic_unsupported_claim_indices(
    source: str,
    claims: list[str],
) -> set[int]:
    return passage_novelty_indices(source, claims) | structured_mismatch_indices(
        source, claims
    )


def supported_claim_indices(source: str, claims: list[str]) -> set[int]:
    source_units = [
        unit
        for source_text in source_support_units(source)
        for unit in response_claims(source_text)
    ]
    normalized_source = [_normalized_content_words(unit) for unit in source_units]
    selected: set[int] = set()
    for index, claim in enumerate(claims):
        if claim_support_conflict(source, claim):
            continue
        normalized_claim = _normalized_content_words(claim)
        if not normalized_claim:
            continue
        if (
            any(
                _near_exact_support(normalized_claim, unit)
                for unit in normalized_source
            )
            or lexical_claim_supported(source, claim)
            or structured_claim_supported(
                source,
                claim,
            )
        ):
            selected.add(index)
    return selected


def hallucination_answer(
    claims: list[str],
    *,
    candidate_indices: set[int],
    verifier_indices: set[int],
    heuristic_indices: set[int],
    supported_indices: set[int],
    accept_verifier_only: bool = False,
) -> tuple[str, int]:
    detector_consensus = candidate_indices & verifier_indices
    detected = detector_consensus | heuristic_indices
    if accept_verifier_only:
        detected |= verifier_indices
    selected = sorted(detected - supported_indices)
    spans = [claims[index] for index in selected[:8]]
    filtered_count = len(detected & supported_indices)
    return json.dumps({"hallucination list": spans}, ensure_ascii=False), filtered_count


def _near_exact_support(claim: str, source_unit: str) -> bool:
    claim_numbers = {token for token in claim.split() if token.isdigit()}
    source_numbers = {token for token in source_unit.split() if token.isdigit()}
    if not claim_numbers <= source_numbers:
        return False
    negations = {"no", "not", "never", "without"}
    if bool(set(claim.split()) & negations) != bool(
        set(source_unit.split()) & negations
    ):
        return False
    if claim in source_unit:
        return True
    similarity = SequenceMatcher(None, claim, source_unit).ratio()
    if similarity >= 0.88:
        return True
    claim_tokens = claim.split()
    source_tokens = source_unit.split()
    overlap = len(set(claim_tokens) & set(source_tokens))
    precision = overlap / len(source_tokens) if source_tokens else 0.0
    recall = overlap / len(claim_tokens) if claim_tokens else 0.0
    token_f1 = (
        2 * precision * recall / (precision + recall) if precision and recall else 0.0
    )
    return token_f1 >= 0.92


def _normalized_words(value: str) -> str:
    return " ".join(_WORD_RE.findall(str(value or "").lower()))


def _normalized_content_words(value: str) -> str:
    return " ".join(
        word
        for word in _WORD_RE.findall(str(value or "").lower())
        if word not in _SUPPORT_STOPWORDS
    )
