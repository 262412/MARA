from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from benchmark.artifact_publication import publish_artifact_contract
from benchmark.execution_plan import (
    JobDefinition,
    build_execution_plan,
    record_submission,
)
from benchmark.reports import write_reports

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "producer_completion_test",
                "documents": [],
                "examples": [
                    {
                        "example_id": "example-1",
                        "question": "question",
                        "answers": ["answer"],
                    }
                ],
                "routes": [{"route_id": "text"}],
            }
        ),
        encoding="utf-8",
    )


def _plan(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    plan_path = tmp_path / "plan.json"
    table_path = tmp_path / "jobs.tsv"
    plan = build_execution_plan(
        [
            JobDefinition(
                "text",
                "producer_completion_test",
                "all",
                0,
                1,
                1,
                60,
                "producer-completion-test",
                manifest,
                tmp_path / "artifacts",
            )
        ],
        output_plan=plan_path,
        output_table=table_path,
        source_sha="clean-sha",
        sample_seed=7,
    )
    record_submission(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        wave_index=0,
        dependency="",
    )
    return plan_path, table_path, plan["jobs"][0]


def _artifact(job: dict[str, Any], output_root: Path) -> Path:
    return write_reports(
        {
            "summary": {
                "suite_name": job["suite_name"],
                "dataset_name": "producer_completion_test",
                "num_examples": 1,
                "num_documents": 0,
            },
            "predictions": [
                {
                    "example_id": example_id,
                    "route": route,
                    "error": None,
                }
                for example_id, route in job["expected_keys"]
            ],
            "documents": [],
        },
        output_root,
        str(job["suite_name"]),
    )


def _runtime_contract(path: Path, *, source_sha: str = "clean-sha") -> None:
    path.write_text(
        json.dumps(
            {
                "contract_id": "benchmark_runtime_contract.v1",
                "source_sha": source_sha,
                "git_dirty": False,
                "slurm_job_id": "12345",
                "execution_job_key": "producer-completion-test",
                "project_root": "/scratch/projects/MARA",
                "runtime_dir": "/fastscratch/runtime",
                "sys.executable": "/fastscratch/runtime/bin/python",
                "slide_cli.__file__": "/scratch/projects/MARA/libs/slide_cli/slide_cli/__init__.py",
                "ktem.__file__": "/scratch/projects/MARA/libs/ktem/ktem/__init__.py",
                "theflow_settings_module": "mara_benchmark_flowsettings",
                "theflow_settings_source": "/fastscratch/runtime/theflow/mara_benchmark_flowsettings.py",
                "theflow_storage_prefix": "/fastscratch/runtime/theflow",
                "KH_APP_DATA_DIR": "/fastscratch/runtime/ktem_app_data",
                "THEFLOW_TEMP_PATH": "/fastscratch/runtime/theflow-temp",
                "UV_PROJECT_ENVIRONMENT": "/fastscratch/runtime/venv",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_producer_completion_reconciliation_updates_ledger_and_is_idempotent(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract)
    runtime_contract_digest = hashlib.sha256(runtime_contract.read_bytes()).hexdigest()

    producer = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        producer_exit_code=0,
        producer_only=True,
    )
    runtime_contract.unlink()
    first = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        slurm_state="COMPLETED",
        slurm_exit_code="0:0",
    )
    second = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        slurm_state="COMPLETED",
        slurm_exit_code="0:0",
    )

    assert producer["valid"] is True
    assert producer["producer_completion_state"] == "VERIFIED"
    assert first == second
    assert first["valid"] is True
    updated = json.loads(plan_path.read_text(encoding="utf-8"))
    updated_job = updated["jobs"][0]
    assert updated_job["state"] == "COMPLETED"
    assert updated_job["slurm_state"] == "COMPLETED"
    assert updated_job["slurm_exit_code"] == "0:0"
    assert updated_job["exit_code"] == "0:0"
    assert updated_job["artifact_complete"] is True
    assert updated_job["artifact_dir"] == str(artifact_dir.resolve())
    assert updated_job["artifact_digest"]
    assert updated_job["runtime_contract_sha256"] == runtime_contract_digest
    assert updated_job["producer_completion_state"] == "VERIFIED"
    assert updated_job["producer_exit_code"] == 0
    assert updated_job["producer_artifact_complete"] is True
    assert updated_job["producer_artifact_digest"] == updated_job["artifact_digest"]
    durable_contract = Path(updated_job["runtime_contract_path"])
    assert durable_contract.is_file()
    assert durable_contract.parent == plan_path.parent / "runtime_contracts"

    header, row = table_path.read_text(encoding="utf-8").splitlines()
    values = dict(zip(header.split("\t"), row.split("\t"), strict=True))
    assert values["slurm_state"] == "COMPLETED"
    assert values["exit_code"] == "0:0"
    assert values["artifact_complete"] == "true"
    assert values["runtime_contract_sha256"] == updated_job["runtime_contract_sha256"]
    assert values["producer_completion_contract"] == "benchmark_producer_completion.v2"
    assert (
        values["completion_reconciliation_contract"]
        == "benchmark_terminal_reconciliation.v2"
    )


def test_reconciliation_rejects_runtime_contract_from_another_source_sha(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract, source_sha="different-sha")
    original_plan = plan_path.read_bytes()
    original_table = table_path.read_bytes()

    with pytest.raises(ValueError, match="source_sha mismatch"):
        reconcile_job_completion(
            plan_path,
            table_path,
            job_key="producer-completion-test",
            job_id="12345",
            artifact_dir=artifact_dir,
            runtime_contract_path=runtime_contract,
            producer_exit_code=0,
            producer_only=True,
        )

    assert plan_path.read_bytes() == original_plan
    assert table_path.read_bytes() == original_table


def test_reconciliation_rejects_key_mismatch_without_false_completion(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    predictions = artifact_dir / "predictions.jsonl"
    predictions.write_text(
        json.dumps({"example_id": "wrong", "route": "text", "error": None}) + "\n",
        encoding="utf-8",
    )
    publish_artifact_contract(artifact_dir)
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract)

    result = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        producer_exit_code=0,
        producer_only=True,
    )

    assert result["valid"] is False
    updated_job = json.loads(plan_path.read_text(encoding="utf-8"))["jobs"][0]
    assert updated_job["state"] == "FAILED"
    assert updated_job["producer_completion_state"] == "FAILED"
    assert updated_job["producer_artifact_complete"] is False
    assert updated_job["producer_artifact_digest"] == ""
    assert "key mismatch" in updated_job["producer_failure_reason"]


def test_producer_completion_fails_plan_when_formal_audit_failed(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    audit_path = artifact_dir / "contract_smoke_audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "contract": "contract_smoke_audit.v2",
                "status": "failed",
                "failed_gates": [],
                "behavior_violations": ["candidate_verifier_audit_failed"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    publish_artifact_contract(artifact_dir)
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract)

    result = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        producer_exit_code=0,
        producer_only=True,
    )

    assert result["valid"] is False
    updated_job = json.loads(plan_path.read_text(encoding="utf-8"))["jobs"][0]
    assert updated_job["state"] == "FAILED"
    assert updated_job["producer_completion_state"] == "FAILED"
    assert updated_job["formal_audit_status"] == "failed"
    assert updated_job["formal_audit_path"] == str(audit_path.resolve())
    assert "formal contract audit status=failed" in updated_job["failure_reason"]


def test_producer_completion_requires_declared_formal_audit(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["jobs"][0]["formal_audit_required"] = True
    from benchmark.execution_plan import _write_plan_and_table

    _write_plan_and_table(plan, plan_path, table_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract)

    result = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        producer_exit_code=0,
        producer_only=True,
    )

    assert result["valid"] is False
    updated_job = json.loads(plan_path.read_text(encoding="utf-8"))["jobs"][0]
    assert updated_job["formal_audit_required"] is True
    assert updated_job["formal_audit_status"] == "not_present"
    assert "required formal contract audit is missing" in updated_job["failure_reason"]


def test_terminal_reconciliation_records_failure_without_runtime_contract(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))

    result = reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        slurm_state="FAILED",
        slurm_exit_code="1:0",
    )

    assert result["valid"] is False
    updated_job = json.loads(plan_path.read_text(encoding="utf-8"))["jobs"][0]
    assert updated_job["state"] == "FAILED"
    assert updated_job["slurm_state"] == "FAILED"
    assert updated_job["slurm_exit_code"] == "1:0"
    assert "runtime contract path is required" in updated_job["failure_reason"]


def test_reconciliation_fails_closed_when_runtime_contract_is_missing(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))

    with pytest.raises(ValueError, match="runtime contract"):
        reconcile_job_completion(
            plan_path,
            table_path,
            job_key="producer-completion-test",
            job_id="12345",
            artifact_dir=artifact_dir,
            producer_exit_code=0,
            producer_only=True,
            slurm_state="COMPLETED",
            slurm_exit_code="0:0",
        )


def test_reconciliation_rejects_conflicting_terminal_replay(tmp_path):
    from benchmark.completion_reconciliation import reconcile_job_completion

    plan_path, table_path, job = _plan(tmp_path)
    artifact_dir = _artifact(job, Path(job["output_root"]))
    runtime_contract = tmp_path / "runtime-contract.json"
    _runtime_contract(runtime_contract)
    reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        producer_exit_code=0,
        producer_only=True,
    )
    reconcile_job_completion(
        plan_path,
        table_path,
        job_key="producer-completion-test",
        job_id="12345",
        artifact_dir=artifact_dir,
        runtime_contract_path=runtime_contract,
        slurm_state="COMPLETED",
        slurm_exit_code="0:0",
    )
    original_plan = plan_path.read_bytes()
    original_table = table_path.read_bytes()

    with pytest.raises(ValueError, match="conflicts"):
        reconcile_job_completion(
            plan_path,
            table_path,
            job_key="producer-completion-test",
            job_id="12345",
            artifact_dir=artifact_dir,
            runtime_contract_path=runtime_contract,
            slurm_state="FAILED",
            slurm_exit_code="1:0",
        )

    assert plan_path.read_bytes() == original_plan
    assert table_path.read_bytes() == original_table


def test_producer_wrappers_reconcile_before_runtime_cleanup_and_export_table():
    runtime_helper = (
        PROJECT_ROOT / "scripts/slurm/benchmark_runtime_isolation.sh"
    ).read_text(encoding="utf-8")
    submitter = (PROJECT_ROOT / "scripts/slurm/submit_fullsystem_jobs.sh").read_text(
        encoding="utf-8"
    )
    for name in ("text_route_rerun.sbatch", "multimodal_route_rerun.sbatch"):
        script = (PROJECT_ROOT / "scripts/slurm" / name).read_text(encoding="utf-8")
        assert "mara_reconcile_benchmark_completion" in script
        assert "MARA_BENCHMARK_ARTIFACT_DIR" in script
        assert script.index("mara_reconcile_benchmark_completion 0") < script.index(
            "mara_cleanup_benchmark_runtime"
        )
    assert "reconcile_benchmark_job.py" in runtime_helper
    assert "--producer-only" in runtime_helper
    assert "MARA_BENCHMARK_COMPLETION_RECORDED" in runtime_helper
    assert "producer completion is unreconciled; preserving runtime for audit" in (
        runtime_helper
    )
    assert "MARA_EXECUTION_TABLE=${JOB_TABLE}" in submitter
    finalizer = (
        PROJECT_ROOT / "scripts/slurm/reconcile_benchmark_job.sbatch"
    ).read_text(encoding="utf-8")
    assert "reconcile-completion" in finalizer
    assert "MARA_RECONCILE_TARGET_JOB_ID" in finalizer
