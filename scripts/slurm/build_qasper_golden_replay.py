#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark.qasper_golden_replay import (  # noqa: E402
    ANCHOR_REPLAY_SHA256,
    RUN_ORDER,
    build_golden_contract,
    project_prediction_file,
    read_projection_jsonl,
    validate_golden_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the immutable QASPER causal-rebuild golden replay."
        )
    )
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--architecture", type=Path, required=True)
    parser.add_argument("--failed", type=Path, required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--contract-output", type=Path, required=True)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Compare source artifacts with existing outputs without writing.",
    )
    args = parser.parse_args()

    source_paths = {
        "anchor_0343ba1": _prediction_path(args.anchor),
        "architecture_fa31e4a": _prediction_path(args.architecture),
        "failed_520ff98": _prediction_path(args.failed),
    }
    projected = {
        label: project_prediction_file(source_paths[label], run_label=label)
        for label in RUN_ORDER
    }
    rows_by_run = {label: projected[label].rows for label in RUN_ORDER}
    legacy_hashes = {
        label: projected[label].legacy_replay_sha256 for label in RUN_ORDER
    }
    if legacy_hashes["anchor_0343ba1"] != ANCHOR_REPLAY_SHA256:
        raise SystemExit(
            "Anchor legacy replay hash does not match the frozen contract."
        )
    contract = build_golden_contract(
        rows_by_run,
        legacy_replay_hashes=legacy_hashes,
        source_artifacts={
            label: str(source_paths[label].resolve()) for label in RUN_ORDER
        },
    )
    rows = [row for label in RUN_ORDER for row in rows_by_run[label]]
    validate_golden_fixture(rows, contract)

    if args.verify_only:
        _verify_existing(args.rows_output, args.contract_output, rows, contract)
    else:
        _write_outputs(args.rows_output, args.contract_output, rows, contract)
    print(json.dumps(_summary(contract), indent=2, sort_keys=True))
    return 0


def _verify_existing(
    rows_path: Path,
    contract_path: Path,
    expected_rows: list[dict[str, object]],
    expected_contract: dict[str, object],
) -> None:
    actual_rows = read_projection_jsonl(rows_path)
    actual_contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_golden_fixture(actual_rows, actual_contract)
    if actual_rows != expected_rows:
        raise SystemExit("Checked-in golden replay rows differ from source artifacts.")
    if actual_contract != expected_contract:
        raise SystemExit(
            "Checked-in golden replay contract differs from source artifacts."
        )


def _write_outputs(
    rows_path: Path,
    contract_path: Path,
    rows: list[dict[str, object]],
    contract: dict[str, object],
) -> None:
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    rows_payload = "".join(
        f"{json.dumps(row, ensure_ascii=False, separators=(',', ':'), sort_keys=True)}\n"
        for row in rows
    )
    rows_path.write_text(rows_payload, encoding="utf-8")
    contract_path.write_text(
        f"{json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _summary(contract: dict[str, object]) -> dict[str, object]:
    runs = contract["runs"]
    protected = contract["protected_sets"]
    assert isinstance(runs, dict)
    assert isinstance(protected, dict)
    return {
        "contract_id": contract["contract_id"],
        "total_projection_count": contract["total_projection_count"],
        "combined_projection_sha256": contract["combined_projection_sha256"],
        "run_counts": {label: runs[label]["prediction_count"] for label in RUN_ORDER},
        "legacy_replay_sha256": {
            label: runs[label]["legacy_replay_sha256"] for label in RUN_ORDER
        },
        "protected_set_counts": {
            name: value["count"] for name, value in protected.items()
        },
    }


def _prediction_path(path: Path) -> Path:
    return path / "predictions.jsonl" if path.is_dir() else path


if __name__ == "__main__":
    raise SystemExit(main())
