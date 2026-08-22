#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark.completion_reconciliation import reconcile_job_completion  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile one completed benchmark producer into its execution ledger."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--job-key", required=True)
    parser.add_argument("--job-id", default=os.environ.get("SLURM_JOB_ID", ""))
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--runtime-contract",
        type=Path,
        default=Path(os.environ["MARA_BENCHMARK_RUNTIME_CONTRACT"])
        if os.environ.get("MARA_BENCHMARK_RUNTIME_CONTRACT")
        else None,
    )
    parser.add_argument("--slurm-state")
    parser.add_argument("--slurm-exit-code")
    parser.add_argument("--producer-exit-code", type=int)
    parser.add_argument("--producer-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = reconcile_job_completion(
        args.plan,
        args.table,
        job_key=args.job_key,
        job_id=args.job_id,
        artifact_dir=args.artifact_dir,
        runtime_contract_path=args.runtime_contract,
        slurm_state=args.slurm_state,
        slurm_exit_code=args.slurm_exit_code,
        producer_exit_code=args.producer_exit_code,
        producer_only=args.producer_only,
    )
    for key in (
        "job_key",
        "job_id",
        "state",
        "slurm_state",
        "exit_code",
        "artifact_complete",
        "artifact_digest",
        "artifact_dir",
        "runtime_contract_path",
        "runtime_contract_sha256",
        "producer_completion_state",
        "producer_exit_code",
        "producer_artifact_complete",
        "producer_artifact_digest",
        "producer_artifact_dir",
        "producer_failure_reason",
        "producer_completion_contract",
        "failure_reason",
        "completion_reconciliation_contract",
        "valid",
    ):
        print(f"{key}={result.get(key, '')}")
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
