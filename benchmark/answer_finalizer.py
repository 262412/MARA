from __future__ import annotations

import json
import re
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .answer_modes import normalize_benchmark_answer_mode

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
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


def finalize_prediction_answer(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    mode: str,
) -> None:
    normalized_mode = normalize_benchmark_answer_mode(mode)
    answer_for_user = str(prediction.get("predicted_answer") or "")
    if normalized_mode == "product":
        answer_for_scoring = answer_for_user
        source = "product_answer"
    else:
        answer_for_scoring = _answer_for_scoring(
            answer_for_user,
            dataset_name=dataset_name,
        )
        source = "deterministic_adapter"

    prediction["answer_for_user"] = answer_for_user
    prediction["answer_for_scoring"] = answer_for_scoring
    prediction["answer_finalization"] = {
        "mode": normalized_mode,
        "source": source,
    }


def _answer_for_scoring(answer: str, *, dataset_name: str) -> str:
    dataset = str(dataset_name or "").lower()
    if "ragtruth" in dataset:
        json_answer = _extract_json_answer(answer)
        if json_answer:
            return json_answer
    cleaned = _clean_scoring_text(extract_final_answer_text(answer))
    if "qampari" in dataset:
        return _comma_list_answer(cleaned)
    return _short_answer(cleaned)


def _extract_json_answer(answer: str) -> str:
    for candidate in _json_candidates(answer):
        parsed = _parse_json(candidate)
        if parsed is not None:
            return json.dumps(parsed, ensure_ascii=False)
    return ""


def _json_candidates(answer: str) -> list[str]:
    text = str(answer or "").strip()
    candidates = [match.group(1).strip() for match in _JSON_BLOCK_RE.finditer(text)]
    candidates.append(text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if 0 <= first_brace < last_brace:
        candidates.append(text[first_brace : last_brace + 1])
    return [candidate for candidate in candidates if candidate]


def _parse_json(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _clean_scoring_text(answer: str) -> str:
    text = str(answer or "").replace("**", "")
    text = _INLINE_CITATION_RE.sub(" ", text)
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


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
    for line in str(text or "").splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def _looks_like_direct_answer(line: str) -> bool:
    words = line.split()
    if len(words) <= 8:
        return True
    if "," in line and len(words) <= 16:
        return True
    return False


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
