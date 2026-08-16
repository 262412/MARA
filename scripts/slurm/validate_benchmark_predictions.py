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


def _qasper_answerability_coverage(
    predictions: list[dict[str, Any]],
    *,
    manifest_path: Path | None = None,
) -> tuple[int, int]:
    usable = [row for row in predictions if _prediction_is_usable(row)]
    if manifest_path is None:
        required = [
            row
            for row in usable
            if str(row.get("answer_type") or "").strip().lower() == "boolean"
        ]
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise SystemExit("QASPER manifest must be a JSON object")
        examples = manifest.get("examples")
        if not isinstance(examples, list):
            raise SystemExit("QASPER manifest must contain an examples list")
        answer_types: dict[str, str] = {}
        for example in examples:
            if not isinstance(example, dict):
                raise SystemExit("QASPER manifest examples must be objects")
            example_id = str(example.get("example_id") or "").strip()
            if not example_id:
                raise SystemExit("QASPER manifest example is missing example_id")
            if example_id in answer_types:
                raise SystemExit(
                    f"QASPER manifest contains duplicate example_id: {example_id}"
                )
            answer_types[example_id] = (
                str(example.get("answer_type") or "").strip().lower()
            )

        required = []
        for row in usable:
            example_id = str(row.get("example_id") or "").strip()
            if not example_id or example_id not in answer_types:
                raise SystemExit(
                    "QASPER prediction example_id is missing from manifest: "
                    f"{example_id or '<missing>'}"
                )
            if answer_types[example_id] != "boolean":
                continue
            prediction_answer_type = str(row.get("answer_type") or "").strip().lower()
            if prediction_answer_type != "boolean":
                raise SystemExit(
                    "QASPER manifest/prediction answer type mismatch for "
                    f"{example_id}: boolean != {prediction_answer_type or '<missing>'}"
                )
            required.append(row)

    covered = 0
    for row in required:
        metadata = row.get("evidence_metadata")
        trace = (
            metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
        )
        if isinstance(trace, dict) and trace:
            covered += 1
    return covered, len(required)


def _manifest_prediction_coverage(
    predictions: list[dict[str, Any]],
    manifest_path: Path,
) -> tuple[int, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SystemExit("benchmark manifest must be a JSON object")
    examples = manifest.get("examples")
    routes = manifest.get("routes")
    if not isinstance(examples, list) or not isinstance(routes, list):
        raise SystemExit("benchmark manifest must contain examples and routes lists")
    example_ids = _unique_manifest_ids(examples, "example_id")
    route_ids = _unique_manifest_ids(routes, "route_id")
    expected_keys = {
        (example_id, route_id) for example_id in example_ids for route_id in route_ids
    }
    observed_keys: set[tuple[str, str]] = set()
    for row in predictions:
        example_id = str(row.get("example_id") or "").strip()
        route_id = str(row.get("route") or "").strip()
        if not example_id or not route_id:
            raise SystemExit("prediction is missing example_id or route")
        key = (example_id, route_id)
        if key in observed_keys:
            raise SystemExit(
                f"benchmark artifact contains duplicate prediction key: {key}"
            )
        observed_keys.add(key)
    if observed_keys != expected_keys:
        missing = sorted(expected_keys - observed_keys)
        unexpected = sorted(observed_keys - expected_keys)
        raise SystemExit(
            "manifest/prediction key mismatch: "
            f"missing={len(missing)} unexpected={len(unexpected)} "
            f"first_missing={missing[:1]} first_unexpected={unexpected[:1]}"
        )
    return len(observed_keys), len(expected_keys)


def _unique_manifest_ids(values: list[Any], field: str) -> list[str]:
    identifiers: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            raise SystemExit("benchmark manifest entries must be objects")
        identifier = str(value.get(field) or "").strip()
        if not identifier:
            raise SystemExit(f"benchmark manifest entry is missing {field}")
        if identifier in identifiers:
            raise SystemExit(
                f"benchmark manifest contains duplicate {field}: {identifier}"
            )
        identifiers.append(identifier)
    if not identifiers:
        raise SystemExit(f"benchmark manifest contains no {field} values")
    return identifiers


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject benchmark artifacts that contain no usable predictions."
    )
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Require predictions to equal the manifest example-by-route cross product.",
    )
    parser.add_argument("--require-all-usable", action="store_true")
    parser.add_argument("--require-hybrid-eligible", action="store_true")
    parser.add_argument("--require-qasper-answerability", action="store_true")
    parser.add_argument(
        "--qasper-manifest",
        type=Path,
        help=(
            "Scope QASPER Boolean answerability coverage to the selected "
            "examples whose manifest answer_type is boolean."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

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
    if args.manifest is not None:
        covered_count, required_count = _manifest_prediction_coverage(
            predictions,
            args.manifest,
        )
        print(f"manifest_prediction_coverage={covered_count}/{required_count}")
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
    if args.qasper_manifest is not None and not args.require_qasper_answerability:
        raise SystemExit("--qasper-manifest requires --require-qasper-answerability")
    if args.require_qasper_answerability:
        covered_count, required_count = _qasper_answerability_coverage(
            predictions,
            manifest_path=args.qasper_manifest,
        )
        print(f"qasper_answerability_coverage={covered_count}/{required_count}")
        if required_count == 0:
            if args.qasper_manifest is not None:
                print("qasper_answerability_status=not_applicable")
                return
            raise SystemExit(
                "formal QASPER validation found no usable boolean predictions"
            )
        if covered_count != required_count:
            raise SystemExit(
                "QASPER answerability trace was missing for "
                f"{required_count - covered_count}/{required_count} "
                "usable boolean predictions"
            )


if __name__ == "__main__":
    main()
