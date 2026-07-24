from __future__ import annotations

import re
from typing import Any

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_DECORATED_NUMBER_RE = re.compile(
    r"^[+-]?(?:[$€£¥]\s*)?\d[\d,]*(?:\.\d+)?%?"
    r"(?:\s*(?:thousand|million|billion|percent|percentage|usd|eur|gbp|jpy))?$",
    re.IGNORECASE,
)
_REPETITION_REQUEST_MARKERS = (
    "repeat",
    "repeated",
    "duplicate",
    "identical",
    "same value",
)
_VISUAL_DATASET_MARKERS = ("slidevqa", "mmdocrag", "vidore", "docvqa")


def deduplicate_final_answer(
    answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
) -> tuple[str, bool, str]:
    text = str(answer or "").strip()
    deduplicated_list = _deduplicate_list_answer(text, prediction)
    if deduplicated_list != text:
        return deduplicated_list, True, "normalized_list_items"
    if not text or len(text) % 2:
        return text, False, ""
    midpoint = len(text) // 2
    first_half = text[:midpoint]
    if first_half != text[midpoint:]:
        return text, False, ""
    if _preserve_repeated_numeric_answer(text, prediction):
        return text, False, ""
    visual_dataset = any(
        name in str(dataset_name or "").lower() for name in _VISUAL_DATASET_MARKERS
    )
    if (
        len(first_half) < 8
        and not visual_dataset
        and not _is_short_numeric_repetition(first_half, prediction, dataset_name)
    ):
        return text, False, ""
    if not first_half:
        return text, False, ""
    return first_half.strip(), True, "exact_repeated_half"


def final_answer_has_duplicate(prediction: dict[str, Any]) -> bool:
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("answer_for_user") or ""
    ).strip()
    if not answer:
        return False
    deduplicated, removed, _kind = deduplicate_final_answer(
        answer,
        prediction=prediction,
        dataset_name=str(prediction.get("dataset_name") or ""),
    )
    return removed and deduplicated != answer


def _deduplicate_list_answer(
    answer: str,
    prediction: dict[str, Any],
) -> str:
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    if answer_type not in {"list", "list_qa"}:
        return answer
    question = str(prediction.get("question") or "").lower()
    if any(marker in question for marker in _REPETITION_REQUEST_MARKERS):
        return answer
    if answer.lstrip().startswith(("{", "[")):
        return answer
    items = [
        re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", item).strip()
        for item in re.split(r"\s*[,;\n]\s*", answer)
    ]
    items = [item for item in items if item]
    if len(items) < 2:
        return answer
    order: list[str] = []
    values: dict[str, str] = {}
    citations: dict[str, list[str]] = {}
    for item in items:
        item_citations = re.findall(r"\d+", " ".join(_INLINE_CITATION_RE.findall(item)))
        value = _INLINE_CITATION_RE.sub("", item).strip()
        key = re.sub(r"\W+", " ", value.casefold()).strip()
        if not key:
            continue
        if key not in values:
            order.append(key)
            values[key] = value
            citations[key] = []
        for citation in item_citations:
            if citation not in citations[key]:
                citations[key].append(citation)
    if len(order) == len(items):
        return answer
    return ", ".join(
        values[key]
        + (
            " " + "".join(f"[{citation}]" for citation in citations[key])
            if citations[key]
            else ""
        )
        for key in order
    )


def _preserve_repeated_numeric_answer(
    answer: str,
    prediction: dict[str, Any],
) -> bool:
    if not answer.isdigit():
        return False
    question = str(prediction.get("question") or "").lower()
    answer_type = str(prediction.get("answer_type") or "").lower()
    return answer_type in {"date", "year"} or any(
        term in question for term in ("date", "year", "when")
    )


def _is_short_numeric_repetition(
    value: str,
    prediction: dict[str, Any],
    dataset_name: str,
) -> bool:
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    numeric_contract = (
        answer_type
        in {
            "calculation",
            "currency",
            "number",
            "numeric",
            "percentage",
            "ratio",
        }
        or "financebench" in str(dataset_name or "").lower()
    )
    return numeric_contract and bool(_DECORATED_NUMBER_RE.fullmatch(value.strip()))
