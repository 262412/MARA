"""CLI boundary for the artifact-bound natural QASPER semantic probe."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.slurm.qasper_natural_semantic_pack_audit import (
    build_audit,
    runtime_code_identity,
)
from scripts.slurm.qasper_natural_semantic_pack_probe import (
    load_probe_inputs,
    load_probe_run_contexts,
    probe_prediction,
)
from scripts.slurm.qasper_retrieval_index_artifact import (
    audit_retrieval_index_binding,
    load_retrieval_index_artifact,
)
from scripts.slurm.qasper_retrieval_index_snapshot import (
    verify_retrieval_index_source_artifacts,
)


def main() -> int:
    args = _arguments()
    rows = load_probe_inputs(args.input, route=args.route)
    semantic_debug_path = args.semantic_debug_input or args.input.with_name(
        "semantic_debug_traces.jsonl"
    )
    trace_rows = _load_semantic_debug_rows(semantic_debug_path)
    artifact = load_retrieval_index_artifact(args.retrieval_index_artifact)
    binding = audit_retrieval_index_binding(
        artifact,
        trace_rows,
        expected_code_sha=args.code_sha,
        expected_index_contract=args.index_contract,
        expected_embedding_contract=args.embedding_contract,
        required_route=args.route,
    )
    source_violations = verify_retrieval_index_source_artifacts(
        artifact,
        predictions_path=args.input,
        semantic_debug_path=semantic_debug_path,
        index_snapshot_path=args.index_snapshot,
    )
    if source_violations:
        binding["status"] = "failed"
        binding["violations"] = list(
            dict.fromkeys([*(binding.get("violations") or []), *source_violations])
        )
    runtime_sha, runtime_clean = runtime_code_identity()
    predictions: list[dict[str, Any]] = []
    _persist_current_state(args, predictions, binding, runtime_sha, runtime_clean)
    if binding["status"] == "matched":
        try:
            contexts = load_probe_run_contexts(
                args.input,
                rows,
                semantic_debug_path=semantic_debug_path,
            )
            predictions = [
                probe_prediction(
                    row,
                    code_sha=args.code_sha,
                    run_context=contexts[_prediction_key(row)],
                )
                for row in rows
            ]
        except Exception as exc:
            audit = _audit(args, predictions, binding, runtime_sha, runtime_clean)
            audit["probe_failure"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "stage2_binding_status": binding["status"],
            }
            _write_probe_outputs(args.output_dir, predictions, audit)
            print(
                f"natural_semantic_pack_failure={type(exc).__name__}:{exc}",
                file=sys.stderr,
            )
            return 1
    audit = _audit(args, predictions, binding, runtime_sha, runtime_clean)
    predictions_path, audit_path = _write_probe_outputs(
        args.output_dir, predictions, audit
    )
    print(f"natural_semantic_pack_status={audit['status']}")
    print(f"natural_semantic_pack_predictions={predictions_path.resolve()}")
    print(f"natural_semantic_pack_audit={audit_path.resolve()}")
    return 0 if audit["status"] == "passed" else 1


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay natural QASPER retrieval records through the canonical pack."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--route", default="text_rag")
    parser.add_argument("--expected-count", type=int, default=6)
    parser.add_argument("--semantic-debug-input", type=Path)
    parser.add_argument("--retrieval-index-artifact", type=Path, required=True)
    parser.add_argument("--index-snapshot", type=Path)
    parser.add_argument("--index-contract", required=True)
    parser.add_argument("--embedding-contract", required=True)
    return parser.parse_args()


def _audit(
    args: argparse.Namespace,
    predictions: list[dict[str, Any]],
    binding: Mapping[str, Any],
    runtime_sha: str,
    runtime_clean: bool,
) -> dict[str, Any]:
    return build_audit(
        predictions,
        code_sha=args.code_sha,
        input_path=args.input,
        expected_count=args.expected_count,
        retrieval_index_binding=binding,
        runtime_code_sha=runtime_sha,
        runtime_worktree_clean=runtime_clean,
    )


def _persist_current_state(
    args: argparse.Namespace,
    predictions: list[dict[str, Any]],
    binding: Mapping[str, Any],
    runtime_sha: str,
    runtime_clean: bool,
) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_probe_outputs(
        args.output_dir,
        predictions,
        _audit(args, predictions, binding, runtime_sha, runtime_clean),
    )


def _write_probe_outputs(
    output_dir: Path,
    predictions: list[dict[str, Any]],
    audit: Mapping[str, Any],
) -> tuple[Path, Path]:
    predictions_path = output_dir / "natural_semantic_pack_predictions.jsonl"
    audit_path = output_dir / "natural_semantic_pack_audit.json"
    predictions_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in predictions
        ),
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps(dict(audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return predictions_path, audit_path


def _load_semantic_debug_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid semantic debug JSONL row {line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(
                f"invalid semantic debug JSONL row {line_number}: object required"
            )
        rows.append(row)
    return rows


def _prediction_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return str(value.get("example_id") or ""), str(value.get("route") or "")


if __name__ == "__main__":
    raise SystemExit(main())
