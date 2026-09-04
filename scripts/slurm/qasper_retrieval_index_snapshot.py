"""Physical snapshot and restore attestations for QASPER retrieval indices."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from ktem.docqa.canonical_serialization import (
    CANONICAL_SERIALIZER_IDENTITY,
    canonical_digest,
)

from scripts.slurm.qasper_retrieval_index_artifact import (
    RESTORE_AUDIT_CONTRACT,
    retrieval_index_artifact_violations,
)

INDEX_SNAPSHOT_CONTRACT = "qasper_index_snapshot.v1"


def index_snapshot_manifest(path: Path) -> dict[str, Any]:
    root = path.resolve()
    if not root.is_dir():
        raise ValueError(f"retrieval_index_snapshot_missing:{root}")
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for candidate in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        relative = candidate.relative_to(root).as_posix()
        if candidate.is_symlink():
            entries.append(
                {"path": relative, "kind": "symlink", "target": os.readlink(candidate)}
            )
            continue
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"retrieval_index_snapshot_entry_invalid:{relative}")
        size = candidate.stat().st_size
        total_bytes += size
        entries.append(
            {
                "path": relative,
                "kind": "file",
                "size": size,
                "sha256": _file_sha256(candidate),
            }
        )
    if not entries:
        raise ValueError("retrieval_index_snapshot_empty")
    return {
        "contract_id": INDEX_SNAPSHOT_CONTRACT,
        "path": str(root),
        "tree_digest": canonical_digest(entries),
        "file_count": sum(entry["kind"] == "file" for entry in entries),
        "symlink_count": sum(entry["kind"] == "symlink" for entry in entries),
        "total_bytes": total_bytes,
    }


def verify_index_snapshot(
    artifact: Mapping[str, Any],
    *,
    snapshot_path: Path | None = None,
) -> list[str]:
    frozen = _mapping(artifact.get("index_snapshot"))
    path = snapshot_path or Path(str(frozen.get("path") or ""))
    try:
        observed = index_snapshot_manifest(path)
    except (OSError, ValueError) as exc:
        return [f"retrieval_index_snapshot_verification_failed:{exc}"]
    reasons = []
    for key in ("tree_digest", "file_count", "symlink_count", "total_bytes"):
        expected = frozen.get(key, 0 if key == "symlink_count" else None)
        if observed.get(key) != expected:
            reasons.append(f"retrieval_index_snapshot_{key}_mismatch")
    return reasons


def verify_retrieval_index_source_artifacts(
    artifact: Mapping[str, Any],
    *,
    predictions_path: Path,
    semantic_debug_path: Path,
    index_snapshot_path: Path | None = None,
) -> list[str]:
    """Require the natural probe to consume its exact producer artifacts."""

    sources = _mapping(artifact.get("source_artifacts"))
    reasons = []
    for name, observed_path in (
        ("predictions", predictions_path),
        ("semantic_debug_traces", semantic_debug_path),
    ):
        source = _mapping(sources.get(name))
        expected_path = Path(str(source.get("path") or ""))
        if expected_path.resolve() != observed_path.resolve():
            reasons.append(f"retrieval_index_source_path_mismatch:{name}")
            continue
        try:
            observed_digest = _file_sha256(observed_path)
        except OSError as exc:
            reasons.append(f"retrieval_index_source_unreadable:{name}:{exc}")
            continue
        if observed_digest != source.get("sha256"):
            reasons.append(f"retrieval_index_source_digest_mismatch:{name}")
    reasons.extend(verify_index_snapshot(artifact, snapshot_path=index_snapshot_path))
    return reasons


def build_retrieval_index_restore_audit(
    artifact: Mapping[str, Any],
    *,
    snapshot_path: Path,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
) -> dict[str, Any]:
    """Attest that a consumer restored the exact frozen physical index tree."""

    frozen = deepcopy(dict(artifact))
    reasons = retrieval_index_artifact_violations(frozen)
    reasons.extend(
        _identity_violations(
            frozen,
            expected_code_sha=expected_code_sha,
            expected_index_contract=expected_index_contract,
            expected_embedding_contract=expected_embedding_contract,
        )
    )
    expected_snapshot = _mapping(frozen.get("index_snapshot"))
    observed_snapshot = _observed_snapshot(snapshot_path, expected_snapshot, reasons)
    payload = {
        "contract_id": RESTORE_AUDIT_CONTRACT,
        "serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
        "status": "matched" if not reasons else "failed",
        "hard_rule": "stop_at_first_divergence",
        "artifact_digest": str(frozen.get("artifact_digest") or ""),
        "code_sha": expected_code_sha,
        "index_contract": expected_index_contract,
        "embedding_contract": expected_embedding_contract,
        "snapshot_path": str(snapshot_path.resolve()),
        "expected_snapshot_tree_digest": str(
            expected_snapshot.get("tree_digest") or ""
        ),
        "observed_snapshot_tree_digest": str(
            observed_snapshot.get("tree_digest") or ""
        ),
        "observed_snapshot": observed_snapshot,
        "violations": list(dict.fromkeys(reasons)),
    }
    payload["audit_digest"] = canonical_digest(payload)
    return payload


def retrieval_index_restore_audit_violations(
    artifact: Mapping[str, Any],
    restore_audit: Mapping[str, Any],
    *,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
) -> list[str]:
    audit = deepcopy(dict(restore_audit))
    reasons = retrieval_index_artifact_violations(artifact)
    if audit.get("contract_id") != RESTORE_AUDIT_CONTRACT:
        reasons.append("retrieval_index_restore_audit_contract_invalid")
    if audit.get("serializer_identity") != CANONICAL_SERIALIZER_IDENTITY:
        reasons.append("retrieval_index_restore_audit_serializer_invalid")
    digest = str(audit.pop("audit_digest", "") or "")
    if not _sha256(digest) or canonical_digest(audit) != digest:
        reasons.append("retrieval_index_restore_audit_digest_mismatch")
    if audit.get("status") != "matched" or audit.get("violations"):
        reasons.append("retrieval_index_restore_audit_not_matched")
    expected_snapshot_digest = str(
        _mapping(artifact.get("index_snapshot")).get("tree_digest") or ""
    )
    expected_values = {
        "artifact_digest": str(artifact.get("artifact_digest") or ""),
        "code_sha": expected_code_sha,
        "index_contract": expected_index_contract,
        "embedding_contract": expected_embedding_contract,
        "expected_snapshot_tree_digest": expected_snapshot_digest,
        "observed_snapshot_tree_digest": expected_snapshot_digest,
    }
    for key, expected in expected_values.items():
        if audit.get(key) != expected:
            reasons.append(f"retrieval_index_restore_audit_{key}_mismatch")
    return list(dict.fromkeys(reasons))


def _observed_snapshot(
    path: Path,
    expected: Mapping[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    try:
        observed = index_snapshot_manifest(path)
    except (OSError, ValueError) as exc:
        reasons.append(f"retrieval_index_snapshot_verification_failed:{exc}")
        return {}
    for key in ("tree_digest", "file_count", "symlink_count", "total_bytes"):
        expected_value = expected.get(key, 0 if key == "symlink_count" else None)
        if observed.get(key) != expected_value:
            reasons.append(f"retrieval_index_snapshot_{key}_mismatch")
    return observed


def _identity_violations(
    artifact: Mapping[str, Any],
    *,
    expected_code_sha: str,
    expected_index_contract: str,
    expected_embedding_contract: str,
) -> list[str]:
    reasons = []
    for key, expected in (
        ("code_sha", expected_code_sha),
        ("index_contract", expected_index_contract),
        ("embedding_contract", expected_embedding_contract),
    ):
        if str(artifact.get(key) or "") != expected:
            reasons.append(f"retrieval_index_artifact_{key}_mismatch")
    return reasons


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
