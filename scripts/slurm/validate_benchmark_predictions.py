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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reject benchmark artifacts that contain no usable predictions."
    )
    parser.add_argument("predictions", type=Path)
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
    if usable_count == 0:
        raise SystemExit("benchmark artifact contains zero usable predictions")


if __name__ == "__main__":
    main()
