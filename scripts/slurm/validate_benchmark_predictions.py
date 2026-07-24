from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _prediction_is_usable(prediction: dict[str, Any]) -> bool:
    if prediction.get("error"):
        return False
    if prediction.get("skipped") or prediction.get("skip_reason"):
        return False
    return True


def _required_hybrid_eligibility(
    predictions: list[dict[str, Any]],
) -> tuple[int, int]:
    decisions: list[dict[str, Any]] = []
    for row in predictions:
        decision = row.get("controller_decision")
        if isinstance(decision, dict):
            decisions.append(decision)
    required: list[bool] = []
    for decision in decisions:
        value = decision.get("required_evidence_route_available")
        if isinstance(value, bool):
            required.append(value)
    return sum(required), len(required)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reject benchmark artifacts that contain no usable predictions."
    )
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--require-all-usable", action="store_true")
    parser.add_argument("--require-hybrid-eligible", action="store_true")
    args = parser.parse_args()

    predictions_path = args.predictions
    predictions = [
        json.loads(line)
        for line in predictions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    usable_count = sum(_prediction_is_usable(row) for row in predictions)
    print(f"total_predictions={len(predictions)}")
    print(f"usable_predictions={usable_count}")
    if not predictions:
        raise SystemExit("benchmark artifact contains zero predictions")
    if args.expected_count is not None and len(predictions) != args.expected_count:
        raise SystemExit(
            f"expected {args.expected_count} predictions but found {len(predictions)}"
        )
    if usable_count == 0:
        raise SystemExit("benchmark artifact contains zero usable predictions")
    if args.require_all_usable and usable_count != len(predictions):
        raise SystemExit(
            "formal benchmark artifact requires every prediction to be usable: "
            f"{usable_count}/{len(predictions)} usable"
        )
    if args.require_hybrid_eligible:
        eligible_count, required_count = _required_hybrid_eligibility(predictions)
        print(f"required_hybrid_eligible={eligible_count}/{required_count}")
        if required_count == 0:
            raise SystemExit(
                "formal hybrid validation found no required-hybrid decisions"
            )
        if eligible_count != required_count:
            raise SystemExit(
                "required hybrid evidence was unavailable for "
                f"{required_count - eligible_count}/{required_count} decisions"
            )


if __name__ == "__main__":
    main()
