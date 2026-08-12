from __future__ import annotations

from typing import Any

from .ragtruth_answer_contract import ragtruth_json_answer


def finalize_ragtruth_if_requested(
    prediction: dict[str, Any],
    raw_answer: str,
    dataset_name: str,
    mode: str,
) -> bool:
    if "ragtruth" not in str(dataset_name or "").strip().lower():
        return False
    json_answer, repair_attempted, repair_succeeded = ragtruth_json_answer(raw_answer)
    source = "ragtruth_contract" if json_answer else "ragtruth_contract_error"
    prediction["answer_for_user"] = json_answer
    prediction["answer_for_scoring"] = json_answer
    prediction["answer_finalization"] = {
        "mode": mode,
        "source": source,
        "repetition_removed": False,
        "repetition_kind": "",
        "ragtruth_json_repair_attempted": repair_attempted,
        "ragtruth_json_repair_succeeded": repair_succeeded,
        "ragtruth_json_valid": bool(json_answer),
        "task_contract_status": "ok" if json_answer else "error",
    }
    return True
