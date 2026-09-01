from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_ROOT / "scripts/slurm/qasper_natural_stage2_canary.sbatch"
RUNTIME_CONTRACT = PROJECT_ROOT / "scripts/slurm/qasper_vllm_runtime_contract.sh"


def test_natural_launcher_uses_the_proven_provider_runtime_contract() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    runtime = RUNTIME_CONTRACT.read_text(encoding="utf-8")

    assert (
        'source "$PROJECT_ROOT/scripts/slurm/qasper_vllm_runtime_contract.sh"'
        in launcher
    )
    assert "mara_configure_qasper_vllm_runtime" in launcher
    assert "mara_preflight_qasper_vllm_runtime" in launcher
    for required in (
        "VLLM_WORKER_MULTIPROC_METHOD=spawn",
        "FLASHINFER_WORKSPACE_BASE=/mnt/fastscratch/users/tbczhang/cache/flashinfer-workspace",
        'FLASHINFER_CUBIN_DIR="$FLASHINFER_WORKSPACE_BASE/.cache/flashinfer/cubins"',
        "TRITON_CACHE_DIR=/mnt/fastscratch/users/tbczhang/cache/triton",
        "CUDA_CACHE_PATH=/mnt/fastscratch/users/tbczhang/cache/cuda",
        "module load cuda/12.8.0-gcc14.2.0",
        '[[ -n "${CUDA_HOME:-}" && -x "$CUDA_HOME/bin/nvcc" ]]',
        '[[ "$(realpath -m "$NINJA_BIN")" == "$(realpath -m "$VLLM_ENV_BIN/ninja")" ]]',
    ):
        assert required in runtime


def test_submission_identity_remains_verifiable_after_slurm_spool_disappears(
    tmp_path: Path,
) -> None:
    from scripts.slurm.qasper_auditor_startup_transaction import (
        write_submission_script_identity,
    )

    script = tmp_path / "stable-submit.sbatch"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    identity_path = tmp_path / "submission_script_identity.json"
    checksum_path = tmp_path / "submission_script.sha256"

    identity = write_submission_script_identity(
        script,
        project_root=tmp_path,
        source_sha="a" * 40,
        output_path=identity_path,
        checksum_path=checksum_path,
    )

    expected_digest = hashlib.sha256(script.read_bytes()).hexdigest()
    assert identity["stable_path"] == str(script.resolve())
    assert identity["relative_path"] == "stable-submit.sbatch"
    assert identity["sha256"] == expected_digest
    assert json.loads(identity_path.read_text(encoding="utf-8")) == identity
    assert checksum_path.read_text(encoding="utf-8") == (
        f"{expected_digest}  {script.resolve()}\n"
    )
    verified = subprocess.run(
        ["sha256sum", "--check", str(checksum_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr


def test_auditor_startup_failure_closes_the_pre_transport_transaction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.slurm.qasper_auditor_startup_transaction import (
        record_auditor_startup_event,
        write_submission_script_identity,
    )

    script = tmp_path / "stable-submit.sbatch"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    identity_path = tmp_path / "submission_script_identity.json"
    write_submission_script_identity(
        script,
        project_root=tmp_path,
        source_sha="b" * 40,
        output_path=identity_path,
        checksum_path=tmp_path / "submission_script.sha256",
    )
    monkeypatch.setenv("MARA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MARA_EXPECTED_SHA", "b" * 40)
    monkeypatch.setenv("MARA_QASPER_CONTRACT_AUDITOR_MODEL", "auditor-model")
    monkeypatch.setenv(
        "MARA_QASPER_CONTRACT_AUDITOR_BASE_URL", "http://127.0.0.1:33001/v1"
    )
    monkeypatch.setenv("MARA_AUDITOR_RUN_MODE", "startup_canary")
    monkeypatch.setenv("MARA_TEXT_RUN_ROOT", str(tmp_path))
    monkeypatch.setenv("SLURM_JOB_ID", "1234")
    monkeypatch.setenv("SLURMD_NODENAME", "gpu-test")
    for name, value in {
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "FLASHINFER_WORKSPACE_BASE": "/cache/flashinfer",
        "FLASHINFER_CUBIN_DIR": "/cache/flashinfer/cubins",
        "TRITON_CACHE_DIR": "/cache/triton",
        "CUDA_CACHE_PATH": "/cache/cuda",
    }.items():
        monkeypatch.setenv(name, value)
    provider_stack = tmp_path / "provider_python_stack.txt"
    provider_stack.write_text(
        "vllm=0.10.2\nflashinfer-python=0.6.11\n", encoding="utf-8"
    )

    transaction_path = tmp_path / "auditor_startup_transaction.json"
    starting = record_auditor_startup_event(
        transaction_path,
        script_identity_path=identity_path,
        status="starting",
        phase="auditor_startup",
    )
    failed = record_auditor_startup_event(
        transaction_path,
        script_identity_path=identity_path,
        status="failed",
        phase="auditor_startup",
        failed_before_transport=True,
        exit_code=1,
        failure_message="provider exited before health check",
    )

    assert starting["status"] == "starting"
    assert failed["status"] == "failed"
    assert failed["transport_status"] == "failed_before_transport"
    assert failed["failed_before_transport"] is True
    assert failed["failure"]["exit_code"] == 1
    assert failed["failure"]["message"] == "provider exited before health check"
    assert [event["status"] for event in failed["events"]] == ["starting", "failed"]
    assert (
        failed["events"][1]["previous_event_digest"]
        == failed["events"][0]["event_digest"]
    )
    assert (
        failed["events"][1]["runtime_artifacts"]["provider_python_stack.txt"]["sha256"]
        == hashlib.sha256(provider_stack.read_bytes()).hexdigest()
    )
    assert failed["transaction_digest"]
    assert json.loads(transaction_path.read_text(encoding="utf-8")) == failed


def test_ready_startup_binds_the_models_artifact(tmp_path: Path, monkeypatch) -> None:
    from scripts.slurm.qasper_auditor_startup_transaction import (
        record_auditor_startup_event,
        write_submission_script_identity,
    )

    script = tmp_path / "stable-submit.sbatch"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    identity_path = tmp_path / "submission_script_identity.json"
    write_submission_script_identity(
        script,
        project_root=tmp_path,
        source_sha="c" * 40,
        output_path=identity_path,
        checksum_path=tmp_path / "submission_script.sha256",
    )
    monkeypatch.setenv("MARA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MARA_EXPECTED_SHA", "c" * 40)
    monkeypatch.setenv("MARA_QASPER_CONTRACT_AUDITOR_MODEL", "auditor-model")
    monkeypatch.setenv(
        "MARA_QASPER_CONTRACT_AUDITOR_BASE_URL", "http://127.0.0.1:33002/v1"
    )
    models = tmp_path / "auditor_models.json"
    models.write_text('{"data": [{"id": "auditor-model"}]}\n', encoding="utf-8")
    transaction_path = tmp_path / "auditor_startup_transaction.json"
    record_auditor_startup_event(
        transaction_path,
        script_identity_path=identity_path,
        status="starting",
        phase="auditor_startup",
    )

    ready = record_auditor_startup_event(
        transaction_path,
        script_identity_path=identity_path,
        status="ready",
        phase="auditor_startup",
        models_artifact_path=models,
    )

    assert ready["status"] == "ready"
    assert ready["transport_status"] == "provider_ready"
    assert ready["events"][-1]["models_artifact"] == {
        "path": str(models.resolve()),
        "sha256": hashlib.sha256(models.read_bytes()).hexdigest(),
    }


def test_startup_canary_and_natural_share_one_auditor_launch_path() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    attempt = launcher.index("record_startup_event starting auditor_startup")
    serve = launcher.index('"$VLLM_BIN" serve "$AUDITOR_MODEL"')
    wait = launcher.index('wait_for_auditor "$AUDITOR_PID"')
    ready = launcher.index("record_startup_event ready auditor_startup")
    startup_only = launcher.index('if [[ "$MARA_AUDITOR_STARTUP_ONLY" == "1" ]]')
    natural = launcher.index(
        'bash "$PROJECT_ROOT/scripts/slurm/text_route_rerun.sbatch"'
    )

    assert attempt < serve < wait < ready < startup_only < natural
    assert "--failed-before-transport" in launcher
    assert "MARA_SUBMISSION_SCRIPT_PATH" in launcher
    assert "submission_script_identity.json" in launcher
