"""Fixture writer for formal QASPER retrieval/index binding tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.artifact_publication import file_sha256
from scripts.slurm.qasper_retrieval_index_artifact import (
    build_retrieval_index_artifact,
)
from scripts.slurm.qasper_retrieval_index_snapshot import (
    build_retrieval_index_restore_audit,
    index_snapshot_manifest,
)

FIXTURE_CODE_SHA = "a" * 40
FIXTURE_INDEX_CONTRACT = f"sha256:{'c' * 64}"
FIXTURE_EMBEDDING_CONTRACT = "d" * 64


def write_retrieval_index_binding(
    run_dir: Path,
    semantic_rows: list[dict[str, Any]],
) -> None:
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["run_provenance"] = {
        "git": {"commit": FIXTURE_CODE_SHA, "dirty": False},
        "index_contract": FIXTURE_INDEX_CONTRACT,
        "embedding_contract": FIXTURE_EMBEDDING_CONTRACT,
    }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    snapshot = run_dir / "retrieval-index-snapshot"
    snapshot.mkdir()
    (snapshot / "index.sqlite").write_bytes(b"fixture-index")
    artifact = build_retrieval_index_artifact(
        semantic_rows,
        code_sha=FIXTURE_CODE_SHA,
        index_contract=FIXTURE_INDEX_CONTRACT,
        embedding_contract=FIXTURE_EMBEDDING_CONTRACT,
        index_snapshot=index_snapshot_manifest(snapshot),
        source_artifacts={
            "predictions": _source(run_dir / "predictions.jsonl"),
            "semantic_debug_traces": _source(
                run_dir / "semantic_debug_traces.jsonl"
            ),
        },
        required_route=str(semantic_rows[0]["route"]),
    )
    (run_dir / "retrieval_index_artifact.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    restore_audit = build_retrieval_index_restore_audit(
        artifact,
        snapshot_path=snapshot,
        expected_code_sha=FIXTURE_CODE_SHA,
        expected_index_contract=FIXTURE_INDEX_CONTRACT,
        expected_embedding_contract=FIXTURE_EMBEDDING_CONTRACT,
    )
    (run_dir / "retrieval_index_restore_audit.json").write_text(
        json.dumps(restore_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": file_sha256(path)}
