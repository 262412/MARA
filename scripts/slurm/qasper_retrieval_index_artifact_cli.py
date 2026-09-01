"""CLI for producing and restoring frozen QASPER retrieval artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark.jsonl import read_jsonl
from scripts.slurm.qasper_retrieval_index_artifact import (
    build_retrieval_index_artifact,
    load_retrieval_index_artifact,
)
from scripts.slurm.qasper_retrieval_index_snapshot import (
    build_retrieval_index_restore_audit,
    index_snapshot_manifest,
)


def _create(args: argparse.Namespace) -> int:
    trace_rows = [
        row
        for row in read_jsonl(args.semantic_debug_traces)
        if isinstance(row, Mapping)
    ]
    artifact = build_retrieval_index_artifact(
        trace_rows,
        code_sha=args.code_sha,
        index_contract=args.index_contract,
        embedding_contract=args.embedding_contract,
        index_snapshot=index_snapshot_manifest(args.index_snapshot),
        source_artifacts={
            "predictions": _source_artifact(args.predictions),
            "semantic_debug_traces": _source_artifact(
                args.semantic_debug_traces
            ),
        },
        required_route=args.route,
    )
    _write_json(args.output, artifact)
    print(f"retrieval_index_artifact={args.output.resolve()}")
    print(f"retrieval_index_artifact_digest={artifact['artifact_digest']}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    artifact = load_retrieval_index_artifact(args.artifact)
    audit = build_retrieval_index_restore_audit(
        artifact,
        snapshot_path=args.index_snapshot,
        expected_code_sha=args.code_sha,
        expected_index_contract=args.index_contract,
        expected_embedding_contract=args.embedding_contract,
    )
    if args.output:
        _write_json(args.output, audit)
    print(f"retrieval_index_artifact_status={audit['status']}")
    if args.output:
        print(f"retrieval_index_restore_audit={args.output.resolve()}")
    for reason in audit["violations"]:
        print(f"retrieval_index_artifact_violation={reason}")
    return 0 if audit["status"] == "matched" else 1


def _source_artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": _file_sha256(path)}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or verify a frozen QASPER retrieval/index artifact."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    _add_common_create_arguments(create)
    create.set_defaults(handler=_create)
    verify = subparsers.add_parser("verify")
    _add_common_verify_arguments(verify)
    verify.set_defaults(handler=_verify)
    args = parser.parse_args()
    return int(args.handler(args))


def _add_common_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--semantic-debug-traces", type=Path, required=True)
    parser.add_argument("--index-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--index-contract", required=True)
    parser.add_argument("--embedding-contract", required=True)
    parser.add_argument("--route", default="text_rag")


def _add_common_verify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--index-snapshot", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--index-contract", required=True)
    parser.add_argument("--embedding-contract", required=True)
    parser.add_argument("--output", type=Path)


if __name__ == "__main__":
    raise SystemExit(main())
