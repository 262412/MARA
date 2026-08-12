from __future__ import annotations

import re
from typing import Any

from ktem.docqa.boolean_claim_verification import canonical_boolean_answer_polarity

from .metrics import is_abstention_answer, normalize_text


def normalize_qasper_contract_answer(
    answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
) -> tuple[str, bool]:
    dataset = str(dataset_name or "").lower()
    if "qasper" not in dataset:
        return answer, False
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    normalized = " ".join(str(answer or "").strip().lower().split())
    exact_boolean = re.fullmatch(r"(yes|no|true|false)[.!?]?", normalized)
    if "qasper_typed" in dataset:
        if answer_type not in {"boolean", "unanswerable"}:
            return answer, False
        if exact_boolean:
            return _canonical_boolean_match(exact_boolean), True
        if is_unanswerable_text(normalized):
            return "unanswerable", True
        return answer, False
    if answer_type == "boolean":
        prefixed_boolean = re.match(r"^(yes|no|true|false)\b", normalized)
        if not prefixed_boolean:
            return answer, False
        return _canonical_boolean_match(prefixed_boolean), True
    if is_unanswerable_text(normalized):
        return "unanswerable", True
    return answer, False


def qasper_typed_label_status(
    answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
) -> str:
    if "qasper_typed" not in str(dataset_name or "").lower():
        return "not_applicable"
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    if answer_type not in {"boolean", "unanswerable"}:
        return "not_applicable"
    return "valid" if valid_qasper_typed_label(answer) else "invalid"


def record_qasper_metadata(
    prediction: dict[str, Any],
    answer: str,
    dataset_name: str,
    contract_normalized: bool,
) -> None:
    finalization = prediction["answer_finalization"]
    finalization["qasper_contract_normalized"] = contract_normalized
    finalization["qasper_typed_label_status"] = qasper_typed_label_status(
        answer,
        prediction=prediction,
        dataset_name=dataset_name,
    )


def valid_qasper_typed_label(value: str) -> bool:
    normalized = " ".join(str(value or "").strip().lower().split())
    return bool(
        canonical_boolean_answer_polarity(normalized)
        and normalize_text(normalized) in {"yes", "no", "true", "false"}
    ) or is_abstention_answer(normalized)


def canonical_semantic_label(value: str) -> str:
    if is_abstention_answer(str(value or "")):
        return "unanswerable"
    polarity = canonical_boolean_answer_polarity(str(value or ""))
    return polarity or normalize_text(value)


def semantic_rewrite_type(before: str, after: str) -> str:
    if before == after:
        return "none"
    before_abstained = before == "unanswerable"
    after_abstained = after == "unanswerable"
    if before_abstained and not after_abstained:
        return "unanswerable_to_polarity"
    if not before_abstained and after_abstained:
        return "polarity_to_unanswerable"
    return "answer_rewrite"


def is_unanswerable_text(answer: str) -> bool:
    return answer.startswith(
        (
            "unanswerable",
            "insufficient evidence",
            "not enough evidence",
            "unable to answer",
            "cannot answer",
        )
    )


def _canonical_boolean_match(match: re.Match[str]) -> str:
    return "yes" if match.group(1) in {"yes", "true"} else "no"
