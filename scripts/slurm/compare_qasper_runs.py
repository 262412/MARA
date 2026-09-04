#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.qasper_fresh_run_diff import (  # noqa: E402
    compare_prediction_runs,
    read_prediction_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two QASPER prediction runs using canonical identities."
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--acceptance", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    acceptance = (
        json.loads(args.acceptance.read_text(encoding="utf-8"))
        if args.acceptance
        else None
    )
    result = compare_prediction_runs(
        read_prediction_jsonl(_prediction_path(args.baseline)),
        read_prediction_jsonl(_prediction_path(args.candidate)),
        acceptance=acceptance,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{payload}\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def _prediction_path(value: Path) -> Path:
    return value / "predictions.jsonl" if value.is_dir() else value


if __name__ == "__main__":
    raise SystemExit(main())
