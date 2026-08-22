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
from benchmark.dependency_repair import record_dependency_repair  # noqa: E402
from benchmark.execution_plan import (  # noqa: E402
    build_execution_plan,
    parse_job_spec,
    record_submission,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or update a frozen Slurm benchmark execution plan."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--output-plan", type=Path, required=True)
    build.add_argument("--output-table", type=Path, required=True)
    build.add_argument("--source-sha", required=True)
    build.add_argument("--sample-seed", type=int, required=True)
    build.add_argument(
        "--job",
        action="append",
        required=True,
        help=(
            "kind,dataset,route,shard_index,num_shards,limit,timeout_seconds,"
            "suite_name,manifest,output_root"
        ),
    )

    record = subparsers.add_parser("record-submission")
    record.add_argument("--plan", type=Path, required=True)
    record.add_argument("--table", type=Path, required=True)
    record.add_argument("--job-key", required=True)
    record.add_argument("--job-id", required=True)
    record.add_argument("--wave-index", type=int, required=True)
    record.add_argument("--dependency", default="")

    repair = subparsers.add_parser("record-dependency-repair")
    repair.add_argument("--plan", type=Path, required=True)
    repair.add_argument("--table", type=Path, required=True)
    repair.add_argument("--job-key", required=True)
    repair.add_argument("--repair-record", type=Path, required=True)

    reconcile = subparsers.add_parser(
        "reconcile-completion",
        aliases=("record-completion",),
    )
    reconcile.add_argument("--plan", type=Path, required=True)
    reconcile.add_argument("--table", type=Path, required=True)
    reconcile.add_argument("--job-key", required=True)
    reconcile.add_argument("--job-id", default=os.environ.get("SLURM_JOB_ID", ""))
    reconcile.add_argument("--artifact-dir", type=Path)
    reconcile.add_argument(
        "--runtime-contract",
        type=Path,
        default=Path(os.environ["MARA_BENCHMARK_RUNTIME_CONTRACT"])
        if os.environ.get("MARA_BENCHMARK_RUNTIME_CONTRACT")
        else None,
    )
    reconcile.add_argument("--slurm-state")
    reconcile.add_argument("--slurm-exit-code")
    reconcile.add_argument("--producer-exit-code", type=int)
    reconcile.add_argument("--producer-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "build":
        build_execution_plan(
            [parse_job_spec(value) for value in args.job],
            output_plan=args.output_plan,
            output_table=args.output_table,
            source_sha=args.source_sha,
            sample_seed=args.sample_seed,
        )
        print(f"execution_plan={args.output_plan}")
        print(f"job_table={args.output_table}")
        return 0

    if args.command == "record-submission":
        record_submission(
            args.plan,
            args.table,
            job_key=args.job_key,
            job_id=args.job_id,
            wave_index=args.wave_index,
            dependency=args.dependency,
        )
        return 0

    if args.command in {"reconcile-completion", "record-completion"}:
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
        print(f"completion_valid={result['valid']}")
        return 0 if result["valid"] else 2

    record_dependency_repair(
        args.plan,
        args.table,
        job_key=args.job_key,
        repair_record_path=args.repair_record,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
