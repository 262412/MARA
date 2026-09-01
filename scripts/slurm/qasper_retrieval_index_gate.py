"""Formal pre-Stage-2 binding for a restored QASPER retrieval artifact."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.slurm.qasper_retrieval_index_artifact import (
    audit_retrieval_index_binding,
    load_retrieval_index_artifact,
)
from scripts.slurm.qasper_retrieval_index_snapshot import (
    retrieval_index_restore_audit_violations,
)


def retrieval_index_binding_audit(
    rows: list[dict[str, Any]],
    *,
    artifact_path: Path | None,
    restore_audit_path: Path | None,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
    required: bool,
) -> dict[str, Any]:
    if artifact_path is None:
        return _failed_or_skipped(
            required=required,
            violations=(
                ["retrieval_index_artifact_required_missing"] if required else []
            ),
        )
    missing_identity = [
        name
        for name, value in (
            ("code_sha", expected_code_sha),
            ("index_contract", expected_index_contract),
            ("embedding_contract", expected_embedding_contract),
        )
        if not value
    ]
    if missing_identity:
        return _failed_or_skipped(
            required=True,
            violations=[
                f"retrieval_index_artifact_expected_{name}_missing"
                for name in missing_identity
            ],
        )
    try:
        artifact = load_retrieval_index_artifact(artifact_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _failed_or_skipped(
            required=True,
            violations=[
                "retrieval_index_artifact_load_failed:"
                f"{type(exc).__name__}:{exc}"
            ],
        )
    restore_violations = _restore_audit_violations(
        artifact,
        restore_audit_path=restore_audit_path,
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
        required=required,
    )
    return audit_retrieval_index_binding(
        artifact,
        rows,
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
        required_route=str(artifact.get("required_route") or ""),
        pre_stage2_violations=restore_violations,
    )


def _failed_or_skipped(
    *,
    required: bool,
    violations: list[str],
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_retrieval_index_binding_audit.v1",
        "status": "failed" if required else "not_required",
        "hard_rule": "stop_at_first_divergence",
        "observations": [],
        "violations": violations,
    }


def _restore_audit_violations(
    artifact: Mapping[str, Any],
    *,
    restore_audit_path: Path | None,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
    required: bool,
) -> list[str]:
    if restore_audit_path is None:
        return ["retrieval_index_restore_audit_required_missing"] if required else []
    try:
        restore_audit = json.loads(restore_audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [
            "retrieval_index_restore_audit_load_failed:"
            f"{type(exc).__name__}:{exc}"
        ]
    if not isinstance(restore_audit, Mapping):
        return ["retrieval_index_restore_audit_object_required"]
    return retrieval_index_restore_audit_violations(
        artifact,
        restore_audit,
        expected_code_sha=expected_code_sha,
        expected_index_contract=expected_index_contract,
        expected_embedding_contract=expected_embedding_contract,
    )
