from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

_NON_SEMANTIC_CONFIG_FIELDS = {
    "backend_health_json",
    "output_dir",
    "suite_name",
}
_SERVICE_ENV_FIELDS = {
    "MARA_BENCHMARK_SERVICE_CONTRACT": "contract",
    "MARA_TEXT_LLM_BASE_URL": "text_llm_endpoint",
    "MARA_RETRIEVAL_BASE_URL": "retrieval_endpoint",
    "MARA_VLM_BASE_URL": "vlm_endpoint",
    "MARA_VLM_MODEL": "vlm_model",
}


def benchmark_run_provenance(
    *,
    manifest_path: str | Path,
    config: Mapping[str, Any],
    repo_root: str | Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    manifest = Path(manifest_path).resolve()
    environment = dict(os.environ if environ is None else environ)
    commit, dirty = _git_state(Path(repo_root).resolve())
    service = {
        output_name: str(environment.get(env_name) or "")
        for env_name, output_name in _SERVICE_ENV_FIELDS.items()
        if str(environment.get(env_name) or "")
    }
    manifest_contract = {"sha256": _file_sha256(manifest)}
    contract_payload: dict[str, Any] = {
        "git": {"commit": commit, "dirty": dirty},
        "manifest": manifest_contract,
        "config": _semantic_config(config),
        "service": {
            key: value
            for key, value in service.items()
            if key not in {"text_llm_endpoint", "retrieval_endpoint", "vlm_endpoint"}
        },
    }
    runtime_payload = {
        **contract_payload,
        "runtime_endpoints": {
            key: value for key, value in service.items() if key.endswith("_endpoint")
        },
    }
    return {
        **contract_payload,
        "manifest": {
            "path": str(manifest),
            **manifest_contract,
        },
        "service": service,
        "contract_hash": _payload_hash(contract_payload),
        "execution_hash": _payload_hash(runtime_payload),
    }


def require_matching_run_contracts(
    left_summary: Mapping[str, Any],
    right_summary: Mapping[str, Any],
) -> None:
    left = str(
        dict(left_summary.get("run_provenance") or {}).get("contract_hash") or ""
    )
    right = str(
        dict(right_summary.get("run_provenance") or {}).get("contract_hash") or ""
    )
    if not left or not right or left != right:
        raise ValueError(
            f"benchmark run contract mismatch: left={left or 'missing'} "
            f"right={right or 'missing'}"
        )


def _semantic_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(dict(config).items())
        if key not in _NON_SEMANTIC_CONFIG_FIELDS
    }


def _git_state(repo_root: Path) -> tuple[str, bool]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    dirty = bool(_git(repo_root, "status", "--porcelain", "--untracked-files=normal"))
    return commit, dirty


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
