from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.artifact_publication import file_sha256


def contract_probe_preflight_violations(
    run_dir: Path,
    *,
    suite_kind: str,
    prediction_count: int,
) -> list[str]:
    if suite_kind != "qasper_debug":
        return []
    probe_path = run_dir / "contract_probe_predictions.jsonl"
    audit = contract_probe_preflight_audit(run_dir, suite_kind=suite_kind)
    if not audit:
        return ["provider_contract_probe_audit_missing"]
    violations: list[str] = []
    if audit.get("contract") != "qasper_provider_contract_probe_audit.v1":
        violations.append("provider_contract_probe_audit_contract_invalid")
    if audit.get("status") != "passed":
        violations.append("provider_contract_probe_audit_failed")
    if audit.get("prediction_count") != prediction_count:
        violations.append("provider_contract_probe_audit_count_mismatch")
    if not probe_path.is_file() or audit.get("source_sha256") != file_sha256(
        probe_path
    ):
        violations.append("provider_contract_probe_audit_digest_mismatch")
    if audit.get("failed_gates") or audit.get("behavior_violations"):
        violations.append("provider_contract_probe_audit_not_clean")
    return violations


def contract_probe_preflight_audit(
    run_dir: Path,
    *,
    suite_kind: str,
) -> dict[str, Any]:
    if suite_kind != "qasper_debug":
        return {}
    path = run_dir / "contract_probe_audit.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {}
        return value
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
