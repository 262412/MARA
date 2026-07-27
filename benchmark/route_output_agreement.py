from __future__ import annotations

from typing import Any

from .metrics import round_metric


def route_output_agreement_rate(
    predictions: list[dict[str, Any]],
) -> float | None:
    grouped: dict[tuple[str, str], list[str]] = {}
    for prediction in predictions:
        example_id = str(prediction.get("example_id") or "").strip()
        route = str(prediction.get("route") or "").strip()
        if not example_id or not route:
            continue
        dataset = str(prediction.get("dataset_name") or "").strip()
        answer = " ".join(
            str(
                prediction.get("answer_for_scoring")
                or prediction.get("predicted_answer")
                or ""
            )
            .lower()
            .split()
        )
        grouped.setdefault((dataset, example_id), []).append(answer)
    comparable = [answers for answers in grouped.values() if len(answers) >= 2]
    if not comparable:
        return None
    return round_metric(
        sum(len(set(answers)) == 1 for answers in comparable) / len(comparable)
    )
