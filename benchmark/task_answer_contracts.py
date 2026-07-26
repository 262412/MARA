from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .qasper_answerability import (
    QASPER_ANSWERABILITY_CONTRACT,
    verify_qasper_answerability,
)


def apply_task_answer_contract(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    llm_factory: Callable[[], Any],
) -> bool:
    """Apply dataset answer invariants after engine output normalization.

    Returns ``True`` when the answer was adjudicated and finalization therefore
    needs to run again before scoring.
    """
    if "qasper" not in str(dataset_name or "").lower() or prediction.get("error"):
        return False
    metadata = prediction.setdefault("evidence_metadata", {})
    existing = metadata.get("qasper_answerability")
    if isinstance(existing, dict) and existing:
        prediction["task_answer_contract"] = {
            "contract_id": QASPER_ANSWERABILITY_CONTRACT,
            "status": "already_applied",
        }
        return False

    candidate = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    result = verify_qasper_answerability(
        llm_factory(),
        question=str(prediction.get("question") or ""),
        evidence=_prediction_evidence(prediction),
        candidate_answer=candidate,
    )
    prediction["predicted_answer"] = result.answer
    metadata["qasper_answerability"] = result.trace
    prediction["task_answer_contract"] = {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": "applied",
    }
    return True


def _prediction_evidence(prediction: dict[str, Any]) -> str:
    values: list[str] = []
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        values.extend(_item_text(item) for item in _records(bundle.get("items")))
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        values.extend(_item_text(item) for item in _records(metadata.get("evidence")))
    values.extend(
        _item_text(item) for item in _records(prediction.get("retrieved_hits"))
    )
    values.append(str(prediction.get("context_preview") or ""))
    return "\n\n".join(dict.fromkeys(value for value in values if value.strip()))


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )
