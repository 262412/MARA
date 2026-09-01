from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.artifact_publication import (  # noqa: E402
    file_sha256,
    verify_artifact_contract,
)
from benchmark.jsonl import iter_jsonl  # noqa: E402


def _prediction_is_usable(prediction: dict[str, Any]) -> bool:
    if prediction.get("error"):
        return False
    if prediction.get("skipped") or prediction.get("skip_reason"):
        return False
    return True


def _required_hybrid_eligibility(
    predictions: Iterable[dict[str, Any]],
) -> tuple[int, int]:
    required: list[bool] = []
    for row in predictions:
        decision = row.get("controller_decision")
        if isinstance(decision, dict):
            value = decision.get("required_evidence_route_available")
            if isinstance(value, bool):
                required.append(value)
    return sum(required), len(required)


def _qasper_answerability_coverage(
    predictions: Iterable[dict[str, Any]],
    *,
    manifest_path: Path | None = None,
) -> tuple[int, int]:
    answer_types: dict[str, str] | None = None
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise SystemExit("QASPER manifest must be a JSON object")
        examples = manifest.get("examples")
        if not isinstance(examples, list):
            raise SystemExit("QASPER manifest must contain an examples list")
        answer_types = {}
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

    covered = 0
    required_count = 0
    for row in predictions:
        if not _prediction_is_usable(row):
            continue
        if answer_types is None:
            if str(row.get("answer_type") or "").strip().lower() != "boolean":
                continue
        else:
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
        required_count += 1
        metadata = row.get("evidence_metadata")
        trace = (
            metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
        )
        if isinstance(trace, dict) and trace:
            covered += 1
    return covered, required_count


def _manifest_prediction_coverage(
    predictions: Iterable[dict[str, Any]],
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
    expected_keys = [
        (example_id, route_id) for example_id in example_ids for route_id in route_ids
    ]
    return _prediction_key_coverage(
        predictions,
        expected_keys,
        label="manifest",
    )


def _expected_key_coverage(
    predictions: Iterable[dict[str, Any]],
    expected_keys_path: Path,
) -> tuple[int, int]:
    payload = json.loads(expected_keys_path.read_text(encoding="utf-8"))
    raw_keys = payload.get("expected_keys") if isinstance(payload, dict) else payload
    if not isinstance(raw_keys, list):
        raise SystemExit("expected keys file must contain an expected_keys list")
    expected_keys: list[tuple[str, str]] = []
    for item in raw_keys:
        if not isinstance(item, list) or len(item) != 2:
            raise SystemExit("expected keys must be [example_id, route] pairs")
        key = (str(item[0]).strip(), str(item[1]).strip())
        if not key[0] or not key[1]:
            raise SystemExit("expected keys cannot contain blank identities")
        if key in expected_keys:
            raise SystemExit(f"expected keys contain a duplicate prediction key: {key}")
        expected_keys.append(key)
    if isinstance(payload, dict):
        expected_count = payload.get("expected_count")
        if expected_count is not None and expected_count != len(expected_keys):
            raise SystemExit(
                "execution contract expected_count does not match expected_keys: "
                f"{expected_count} != {len(expected_keys)}"
            )
        expected_digest = str(payload.get("expected_key_sha256") or "")
        if expected_digest and expected_digest != _key_sha256(expected_keys):
            raise SystemExit("execution contract expected_key_sha256 does not match expected_keys")
        manifest_path = payload.get("manifest")
        manifest_digest = str(payload.get("manifest_sha256") or "")
        if manifest_path and manifest_digest:
            if file_sha256(Path(str(manifest_path))) != manifest_digest:
                raise SystemExit(
                    "execution contract manifest_sha256 does not match the manifest"
                )
    return _prediction_key_coverage(
        predictions,
        expected_keys,
        label="execution contract",
    )


def _key_sha256(keys: list[tuple[str, str]]) -> str:
    canonical = "\n".join(
        f"{example_id}\t{route_id}" for example_id, route_id in sorted(keys)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _prediction_key_coverage(
    predictions: Iterable[dict[str, Any]],
    expected_keys: list[tuple[str, str]],
    *,
    label: str,
) -> tuple[int, int]:
    expected_key_set = set(expected_keys)
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
    if observed_keys != expected_key_set:
        missing = sorted(expected_key_set - observed_keys)
        unexpected = sorted(observed_keys - expected_key_set)
        raise SystemExit(
            f"{label}/prediction key mismatch: "
            f"missing={len(missing)} unexpected={len(unexpected)} "
            f"first_missing={missing[:1]} first_unexpected={unexpected[:1]}"
        )
    return len(observed_keys), len(expected_key_set)


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


def _iter_prediction_dicts(path: Path) -> Iterator[dict[str, Any]]:
    for value in iter_jsonl(path):
        if not isinstance(value, dict):
            raise SystemExit("benchmark JSONL predictions must contain JSON objects")
        yield dict(value)


def _prediction_counts(path: Path) -> tuple[int, int]:
    total_count = 0
    usable_count = 0
    for prediction in _iter_prediction_dicts(path):
        total_count += 1
        usable_count += _prediction_is_usable(prediction)
    return total_count, usable_count


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject benchmark artifacts that contain no usable predictions."
    )
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Require predictions to equal the complete manifest example-by-route "
            "cross product; use this only for a merged full-run artifact."
        ),
    )
    parser.add_argument(
        "--expected-keys-file",
        type=Path,
        help="Require predictions to equal the selected job execution contract.",
    )
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--require-complete-marker",
        action="store_true",
        help="Require and verify artifact_complete.json and all published digests.",
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

    if args.manifest is not None and args.expected_keys_file is not None:
        raise SystemExit("--manifest and --expected-keys-file are mutually exclusive")
    if args.require_complete_marker and args.artifact_dir is None:
        raise SystemExit("--require-complete-marker requires --artifact-dir")
    if args.require_complete_marker:
        verify_artifact_contract(args.artifact_dir)

    predictions_path = args.predictions
    total_count, usable_count = _prediction_counts(predictions_path)
    print(f"total_predictions={total_count}")
    print(f"usable_predictions={usable_count}")
    if not total_count:
        raise SystemExit("benchmark artifact contains zero predictions")
    if args.expected_count is not None and total_count != args.expected_count:
        raise SystemExit(
            f"expected {args.expected_count} predictions but found {total_count}"
        )
    if args.manifest is not None:
        covered_count, required_count = _manifest_prediction_coverage(
            _iter_prediction_dicts(predictions_path),
            args.manifest,
        )
        print(f"manifest_prediction_coverage={covered_count}/{required_count}")
    if args.expected_keys_file is not None:
        covered_count, required_count = _expected_key_coverage(
            _iter_prediction_dicts(predictions_path),
            args.expected_keys_file,
        )
        print(f"execution_key_coverage={covered_count}/{required_count}")
    if usable_count == 0:
        raise SystemExit("benchmark artifact contains zero usable predictions")
    if args.require_all_usable and usable_count != total_count:
        raise SystemExit(
            "formal benchmark artifact requires every prediction to be usable: "
            f"{usable_count}/{total_count} usable"
        )
    if args.require_hybrid_eligible:
        eligible_count, required_count = _required_hybrid_eligibility(
            _iter_prediction_dicts(predictions_path)
        )
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
            _iter_prediction_dicts(predictions_path),
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
