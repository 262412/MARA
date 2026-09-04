from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBMIT_FULLSYSTEM = PROJECT_ROOT / "scripts/slurm/submit_fullsystem_jobs.sh"
CLEANUP_BARRIER = PROJECT_ROOT / "scripts/slurm/benchmark_cleanup_barrier.sbatch"
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"
MULTIMODAL_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/multimodal_route_rerun.sbatch"
RUNTIME_HELPER = PROJECT_ROOT / "scripts/slurm/benchmark_runtime_isolation.sh"
SERVICE_RUNTIME_PREFLIGHT = PROJECT_ROOT / "scripts/slurm/service_runtime_preflight.sh"


def _require_posix_bash() -> None:
    if os.name == "nt":
        pytest.skip("Slurm shell validation requires a POSIX bash environment")


def _write_runtime_receipts(runtime_list: Path) -> Path:
    receipt_list = runtime_list.with_name("runtime-receipts.txt")
    receipt_paths: list[Path] = []
    for runtime_line in runtime_list.read_text(encoding="utf-8").splitlines():
        runtime_path = Path(runtime_line)
        job_id = runtime_path.name.removeprefix("job")
        receipt_path = runtime_list.parent / f"{job_id}.receipt"
        receipt_path.write_text(
            f"slurm_job_id={job_id}\nruntime_dir={runtime_path}\n",
            encoding="utf-8",
        )
        receipt_paths.append(receipt_path)
    receipt_list.write_text(
        "".join(f"{receipt_path}\n" for receipt_path in receipt_paths),
        encoding="utf-8",
    )
    return receipt_list


def _run_barrier(
    runtime_list: Path, **variables: str
) -> subprocess.CompletedProcess[str]:
    receipt_list = _write_runtime_receipts(runtime_list)
    environment = os.environ.copy()
    environment.update(
        {
            "MARA_RUNTIME_DIR_LIST": str(runtime_list),
            "MARA_RUNTIME_RECEIPT_LIST": str(receipt_list),
            "MARA_CLEANUP_BARRIER_WAIT_SECONDS": "0",
            **variables,
        }
    )
    return subprocess.run(
        ["bash", str(CLEANUP_BARRIER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _quota_output(used_inodes: int, soft_limit: int) -> str:
    return (
        "Disk quotas for usr test (uid 1):\n"
        "     Filesystem  kbytes quota limit grace files quota limit grace\n"
        "/mnt/fastscratch\n"
        f"                0 0 0 - {used_inodes} {soft_limit} 700000 -\n"
    )


def _write_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def _write_text_service_runtime(hpc_home: Path) -> None:
    for path in (
        hpc_home / "serve_qwen3_8b.sh",
        hpc_home / "serve_retrieval.sh",
        hpc_home / ".venv/bin/python",
        hpc_home / ".venv/bin/vllm",
        hpc_home / ".venv-retrieval/bin/python",
    ):
        _write_executable(path)
    for path in (
        hpc_home / "env.sh",
        hpc_home / "env-retrieval.sh",
        hpc_home / "configure_mara_local_models.py",
        hpc_home / "local_retrieval_server.py",
        hpc_home / ".venv/bin/activate",
        hpc_home / ".venv-retrieval/bin/activate",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime fixture\n", encoding="utf-8")


def test_service_runtime_preflight_rejects_broken_environment_symlinks(tmp_path):
    _require_posix_bash()
    hpc_home = tmp_path / "mara-hpc"
    hpc_home.mkdir()
    for path in (
        hpc_home / "serve_qwen3_8b.sh",
        hpc_home / "serve_retrieval.sh",
    ):
        _write_executable(path)
    for path in (
        hpc_home / "env.sh",
        hpc_home / "env-retrieval.sh",
        hpc_home / "configure_mara_local_models.py",
        hpc_home / "local_retrieval_server.py",
    ):
        path.write_text("runtime fixture\n", encoding="utf-8")
    (hpc_home / ".venv").symlink_to(tmp_path / "missing-vllm-environment")
    (hpc_home / ".venv-retrieval").symlink_to(
        tmp_path / "missing-retrieval-environment"
    )

    result = subprocess.run(
        ["bash", str(SERVICE_RUNTIME_PREFLIGHT), str(hpc_home), "text"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "service_runtime_preflight_failed=missing_file" in result.stderr
    assert str(hpc_home / ".venv/bin/activate") in result.stderr


def test_service_runtime_preflight_accepts_complete_text_runtime(tmp_path):
    _require_posix_bash()
    hpc_home = tmp_path / "mara-hpc"
    _write_text_service_runtime(hpc_home)

    result = subprocess.run(
        ["bash", str(SERVICE_RUNTIME_PREFLIGHT), str(hpc_home), "text"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "service_runtime_preflight=ok mode=text" in result.stdout
    assert "service_runtime_digest=" in result.stdout


def test_service_runtime_preflight_runs_before_runtime_or_plan_creation():
    launcher = SUBMIT_FULLSYSTEM.read_text(encoding="utf-8")
    text_wrapper = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")
    multimodal_wrapper = MULTIMODAL_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert launcher.index(
        'mara_preflight_service_runtime "$HPC_HOME" full'
    ) < launcher.index('"$PLAN_PYTHON" "$PLAN_BUILDER" build')
    text_preflight = text_wrapper.index(
        'mara_preflight_service_runtime "$HPC_HOME" text'
    )
    multimodal_preflight = multimodal_wrapper.index(
        'mara_preflight_service_runtime "$HPC_HOME" multimodal'
    )
    assert text_preflight < text_wrapper.index("trap cleanup EXIT")
    assert text_preflight < text_wrapper.index("mara_configure_benchmark_runtime")
    assert multimodal_preflight < multimodal_wrapper.index("trap cleanup EXIT")
    assert multimodal_preflight < multimodal_wrapper.index(
        "mara_configure_benchmark_runtime"
    )


def test_runtime_path_characterization_reaches_barrier_with_fake_sbatch(tmp_path):
    _require_posix_bash()
    launcher = SUBMIT_FULLSYSTEM.read_text(encoding="utf-8")
    function_start = launcher.index("runtime_dir_for_job()")
    function_end = launcher.index("\n}\n", function_start) + 3
    runtime_function = launcher[function_start:function_end]

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_sbatch = fake_bin / "sbatch"
    fake_sbatch.write_text(
        "#!/usr/bin/env bash\n" "printf '1234\\n'\n",
        encoding="utf-8",
    )
    fake_sbatch.chmod(0o755)
    runtime_root = tmp_path / "benchmark-runtime"
    runtime_list = tmp_path / "runtime-list.txt"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    result = subprocess.run(
        [
            "bash",
            "-c",
            f"""
            set -euo pipefail
            RUNTIME_ROOT={runtime_root}
            {runtime_function}
            job_id="$(sbatch --parsable --job-name=suite)"
            runtime_dir="$(runtime_dir_for_job text suite "$job_id")"
            printf '%s\\n' "$runtime_dir" > {runtime_list}
            """,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    actual_runtime = runtime_root / "suite-1234" / "job1234"
    assert runtime_list.read_text(encoding="utf-8") == f"{actual_runtime}\n"

    actual_runtime.mkdir(parents=True)
    barrier_result = _run_barrier(runtime_list)
    assert barrier_result.returncode == 2
    assert f"runtime_pending={actual_runtime}" in barrier_result.stdout
    assert "runtime_cleanup_barrier_failed=" in barrier_result.stderr
    assert actual_runtime.is_dir()


def test_runtime_helper_writes_producer_owned_receipt(tmp_path):
    _require_posix_bash()
    runtime_root = tmp_path / "benchmark-runtime"
    receipt_dir = tmp_path / "runtime-receipts"
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"""
            set -euo pipefail
            export MARA_PROJECT_ROOT={PROJECT_ROOT}
            export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
            export MARA_BENCHMARK_RUNTIME_RECEIPT_DIR={receipt_dir}
            export SLURM_JOB_ID=1234
            source {RUNTIME_HELPER}
            mara_configure_benchmark_runtime producer-suite
            test "$MARA_BENCHMARK_RUNTIME_RECEIPT_PATH" = "{receipt_dir}/1234.receipt"
            cat "$MARA_BENCHMARK_RUNTIME_RECEIPT_PATH"
            """,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "slurm_job_id=1234",
        f"runtime_dir={runtime_root}/producer-suite/job1234",
    ]


def test_producer_runtime_receipt_reaches_barrier_and_fails_closed(tmp_path):
    _require_posix_bash()
    runtime_root = tmp_path / "benchmark-runtime"
    receipt_dir = tmp_path / "runtime-receipts"
    producer = subprocess.run(
        [
            "bash",
            "-c",
            f"""
            set -euo pipefail
            export MARA_PROJECT_ROOT={PROJECT_ROOT}
            export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
            export MARA_BENCHMARK_RUNTIME_RECEIPT_DIR={receipt_dir}
            export SLURM_JOB_ID=1234
            source {RUNTIME_HELPER}
            mara_configure_benchmark_runtime producer-suite
            printf '%s\n' "$MARA_BENCHMARK_RUNTIME_DIR"
            """,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert producer.returncode == 0, producer.stderr
    runtime_dir = Path(producer.stdout.strip())
    receipt_path = receipt_dir / "1234.receipt"
    runtime_list = tmp_path / "runtime-list.txt"
    receipt_list = tmp_path / "receipt-list.txt"
    runtime_list.write_text(f"{runtime_dir}\n", encoding="utf-8")
    receipt_list.write_text(f"{receipt_path}\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "MARA_RUNTIME_DIR_LIST": str(runtime_list),
            "MARA_RUNTIME_RECEIPT_LIST": str(receipt_list),
            "MARA_CLEANUP_BARRIER_WAIT_SECONDS": "0",
        }
    )

    barrier = subprocess.run(
        ["bash", str(CLEANUP_BARRIER)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert barrier.returncode == 2
    assert f"runtime_pending={runtime_dir}" in barrier.stdout
    assert "runtime_cleanup_barrier_failed=" in barrier.stderr
    assert runtime_dir.is_dir()


def test_runtime_producer_path_contract_explains_job_id_suffix():
    launcher = SUBMIT_FULLSYSTEM.read_text(encoding="utf-8")
    text_wrapper = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")
    runtime_helper = RUNTIME_HELPER.read_text(encoding="utf-8")

    assert 'SUITE_NAME="${NAME}-${RUN_ID}"' in text_wrapper
    assert 'task_slug="$(mara_benchmark_slug "$(mara_benchmark_task_id)")"' in (
        runtime_helper
    )
    assert "printf 'job%s' \"$SLURM_JOB_ID\"" in runtime_helper
    assert 'runtime_suite="${suite}-${job_id}"' in launcher
    assert 'WAVE_RUNTIME_DIRS+=("$runtime_dir")' in launcher
    assert "MARA_BENCHMARK_RUNTIME_RECEIPT_DIR=${RECEIPT_ROOT}" in launcher
    assert "MARA_RUNTIME_RECEIPT_LIST=${runtime_receipt_list}" in launcher
    assert launcher.count("MARA_BENCHMARK_RUNTIME_RECEIPT_DIR=${RECEIPT_ROOT}") == 2


def test_cleanup_barrier_fault_injection_fails_closed_for_leftover_runtime(tmp_path):
    _require_posix_bash()
    runtime_dir = tmp_path / "benchmark-runtime" / "suite-1234" / "job1234"
    runtime_dir.mkdir(parents=True)
    runtime_list = tmp_path / "runtime-list.txt"
    runtime_list.write_text(f"{runtime_dir}\n", encoding="utf-8")

    result = _run_barrier(runtime_list)
    assert result.returncode == 2
    assert f"runtime_pending={runtime_dir}" in result.stdout
    assert "runtime_cleanup_barrier_failed=" in result.stderr
    assert runtime_dir.is_dir()


def test_cleanup_barrier_fault_injection_accepts_absent_runtime_without_slurm(
    tmp_path,
):
    _require_posix_bash()
    runtime_list = tmp_path / "runtime-list.txt"
    runtime_list.write_text(
        f"{tmp_path / 'already-clean' / 'suite' / 'job1234'}\n",
        encoding="utf-8",
    )

    result = _run_barrier(runtime_list)
    assert result.returncode == 0, result.stderr
    assert "runtime_cleanup_verified=" in result.stdout
    assert "sbatch" not in CLEANUP_BARRIER.read_text(encoding="utf-8")


def test_cleanup_barrier_inode_admission_fault_injection_rejects_next_wave(
    tmp_path,
):
    _require_posix_bash()
    runtime_list = tmp_path / "runtime-list.txt"
    runtime_list.write_text(
        f"{tmp_path / 'already-clean' / 'suite' / 'job1234'}\n",
        encoding="utf-8",
    )

    result = _run_barrier(
        runtime_list,
        MARA_NEXT_WAVE_JOB_COUNT="1",
        MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE="92000",
        MARA_FULLSYSTEM_MIN_FREE_INODES="50000",
        MARA_CLEANUP_BARRIER_QUOTA_LINE=_quota_output(100000, 200000),
    )
    assert result.returncode == 2
    assert "inode_admission" in result.stderr
    assert "next_wave_jobs=1" in result.stderr


def test_cleanup_barrier_rejects_missing_runtime_receipt(tmp_path):
    _require_posix_bash()
    runtime_dir = tmp_path / "benchmark-runtime" / "suite" / "job1234"
    runtime_list = tmp_path / "runtime-list.txt"
    runtime_list.write_text(f"{runtime_dir}\n", encoding="utf-8")
    receipt_list = tmp_path / "missing-runtime-receipts.txt"
    receipt_list.write_text(f"{tmp_path / 'missing.receipt'}\n", encoding="utf-8")

    result = _run_barrier(runtime_list, MARA_RUNTIME_RECEIPT_LIST=str(receipt_list))
    assert result.returncode == 2
    assert "missing_runtime_receipt" in result.stderr


def test_cleanup_barrier_rejects_corrupt_runtime_receipt(tmp_path):
    _require_posix_bash()
    runtime_dir = tmp_path / "benchmark-runtime" / "suite" / "job1234"
    runtime_list = tmp_path / "runtime-list.txt"
    runtime_list.write_text(f"{runtime_dir}\n", encoding="utf-8")
    receipt_path = tmp_path / "corrupt.receipt"
    receipt_path.write_text("runtime_dir=/wrong/path\n", encoding="utf-8")
    receipt_list = tmp_path / "corrupt-runtime-receipts.txt"
    receipt_list.write_text(f"{receipt_path}\n", encoding="utf-8")

    result = _run_barrier(runtime_list, MARA_RUNTIME_RECEIPT_LIST=str(receipt_list))
    assert result.returncode == 2
    assert "corrupt_runtime_receipt" in result.stderr


def test_fullsystem_submission_admits_first_wave_then_barrier_gates_next_wave():
    launcher = SUBMIT_FULLSYSTEM.read_text(encoding="utf-8")

    assert (
        'INODES_PER_JOB_RESERVE="${MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE:-92000}"'
        in launcher
    )
    assert "if ((job_index == 0)); then" in launcher
    assert 'submit_wave_barrier "$NEXT_WAVE_SIZE"' in launcher
    assert "MARA_NEXT_WAVE_JOB_COUNT=${next_wave_job_count}" in launcher
    assert 'dependency_args="--dependency=afterok:${PREVIOUS_BARRIER}"' in launcher
    assert "per_job_reserve=${INODES_PER_JOB_RESERVE}" in launcher
    assert ":-20000" not in launcher
