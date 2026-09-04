from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .ragtruth_answer_contract import ragtruth_json_answer

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_FINAL_ANSWER_PREFIX_RE = re.compile(
    r"^\s*(?:\*{0,2}\s*)?(?:final\s+answer|answer|最终答案|最终回答)"
    r"(?:\s*\*{0,2})?\s*[:：]\s*",
    re.IGNORECASE,
)
_ANSWER_PRESENTATION_PREFIX_RE = re.compile(
    r"^\s*(?:the\s+answer\s+is|the\s+answer\s+was|answer\s+is|answer\s+was|"
    r"it\s+is|it\s+was)\s+",
    re.IGNORECASE,
)
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_YES_NO_RATIONALE_RE = re.compile(r"^\s*(yes|no)[.!?]\s+(.+)", re.IGNORECASE)
_YES_NO_ONLY_RE = re.compile(r"^\s*(yes|no)[.!?]?\s*$", re.IGNORECASE)
_INITIAL_PERIOD_TOKEN = "__MARA_INITIAL_PERIOD__"
_INITIAL_PERIOD_RE = re.compile(r"\b([A-Z])\.")


def select_scoring_answer(
    *,
    answer_for_user: str,
    answer_for_scoring_source: str,
    structured_answer: dict[str, Any] | None,
    truncated_answer: str,
    dataset_name: str,
    mode: str,
    preserve_semantic_answer: bool = False,
) -> tuple[str, str]:
    if mode == "product":
        return answer_for_user, "product_answer"
    if preserve_semantic_answer:
        return (
            answer_for_scoring(
                answer_for_scoring_source,
                dataset_name=dataset_name,
                preserve_semantic_answer=True,
            ),
            "terminal_projection_adapter",
        )
    if structured_answer is not None:
        return (
            answer_for_scoring(
                structured_answer["answer"],
                dataset_name=dataset_name,
                preserve_semantic_answer=preserve_semantic_answer,
            ),
            "structured_adapter",
        )
    if truncated_answer:
        return (
            answer_for_scoring(
                truncated_answer,
                dataset_name=dataset_name,
                preserve_semantic_answer=preserve_semantic_answer,
            ),
            "truncated_structured_adapter",
        )
    return (
        answer_for_scoring(
            answer_for_scoring_source,
            dataset_name=dataset_name,
            preserve_semantic_answer=preserve_semantic_answer,
        ),
        "deterministic_adapter",
    )


def answer_for_scoring(
    answer: str,
    *,
    dataset_name: str,
    preserve_semantic_answer: bool = False,
) -> str:
    dataset = str(dataset_name or "").lower()
    if "ragtruth" in dataset:
        json_answer, _, _ = ragtruth_json_answer(answer)
        if json_answer:
            return json_answer
    if preserve_semantic_answer:
        return _terminal_projection_answer(answer)
    cleaned = _clean_scoring_text(extract_final_answer_text(answer))
    if "qampari" in dataset:
        return _comma_list_answer(cleaned)
    return _short_answer(cleaned)


def _terminal_projection_answer(answer: str) -> str:
    """Apply only semantics-preserving cleanup to an immutable terminal answer."""

    text = _INLINE_CITATION_RE.sub(" ", str(answer or ""))
    normalized = " ".join(text.split())
    return _strip_terminal_period(normalized)


def _clean_scoring_text(answer: str) -> str:
    text = str(answer or "").replace("**", "")
    text = _INLINE_CITATION_RE.sub(" ", text)
    lines = [_clean_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _clean_line(line: str) -> str:
    text = _FINAL_ANSWER_PREFIX_RE.sub("", str(line or ""))
    text = _LIST_PREFIX_RE.sub("", text)
    text = _ANSWER_PRESENTATION_PREFIX_RE.sub("", text)
    return " ".join(text.split())


def _comma_list_answer(answer: str) -> str:
    first_line = _first_nonempty_line(answer)
    if "," in first_line:
        parts = [part.strip().rstrip(".") for part in first_line.split(",")]
        return ", ".join(part for part in parts if part)
    return _short_answer(answer)


def _short_answer(answer: str) -> str:
    first_line = _first_nonempty_line(answer)
    if not first_line:
        return ""
    yes_no_rationale = _yes_no_rationale_answer(answer)
    if yes_no_rationale:
        return yes_no_rationale
    if _looks_like_direct_answer(first_line):
        return _strip_terminal_period(first_line)
    return _strip_terminal_period(_first_sentence(first_line))


def _yes_no_rationale_answer(answer: str) -> str:
    lines = [line.strip() for line in str(answer or "").splitlines() if line.strip()]
    if not lines:
        return ""
    same_line = _YES_NO_RATIONALE_RE.match(lines[0])
    if same_line:
        return _format_yes_no_rationale(same_line.group(1), same_line.group(2))
    first_line = _YES_NO_ONLY_RE.fullmatch(lines[0])
    if first_line and len(lines) > 1:
        return _format_yes_no_rationale(first_line.group(1), lines[1])
    return ""


def _format_yes_no_rationale(polarity: str, rationale: str) -> str:
    sentence = _first_sentence(str(rationale or "").strip())
    if not sentence:
        return ""
    return _strip_terminal_period(f"{polarity.capitalize()}. {sentence}")


def _first_nonempty_line(text: str) -> str:
    return next(
        (line.strip() for line in str(text or "").splitlines() if line.strip()),
        "",
    )


def _looks_like_direct_answer(line: str) -> bool:
    words = line.split()
    return len(words) <= 8 or ("," in line and len(words) <= 16)


def _first_sentence(text: str) -> str:
    protected = _INITIAL_PERIOD_RE.sub(rf"\1{_INITIAL_PERIOD_TOKEN}", text)
    match = re.search(r"(?<=[.!?])\s+", protected)
    if not match:
        return text
    return protected[: match.start()].replace(_INITIAL_PERIOD_TOKEN, ".")


def _strip_terminal_period(text: str) -> str:
    value = str(text or "").strip()
    if value.endswith(".") and not value.endswith("..."):
        return value[:-1].strip()
    return value
