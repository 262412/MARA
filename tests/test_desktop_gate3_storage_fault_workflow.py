from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_native_package_jobs_prove_storage_fault_recovery_without_path_leaks() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "--smoke-test-gate3-disk-full" in commands
        assert "--smoke-test-gate3-database-lock" in commands

    linux_commands = _commands(jobs["package-linux-22"])
    assert "--phase disk-full-recovered" in linux_commands
    assert "--phase database-lock-recovered" in linux_commands
    assert '! grep -F "/tmp/mara-desktop/data/MARA"' in linux_commands

    windows = jobs["package-windows"]
    windows_commands = _commands(windows)
    assert '"disk_full_exit_code=$($diskFullProcess.ExitCode)"' in windows_commands
    assert (
        '"database_lock_exit_code=$($databaseLockProcess.ExitCode)"' in windows_commands
    )
    assert "Select-String -Path $diskFullStderr -SimpleMatch $dataRoot" in (
        windows_commands
    )
    assert "Select-String -Path $databaseLockStderr -SimpleMatch $dataRoot" in (
        windows_commands
    )
    diagnostics = next(
        step
        for step in windows["steps"]
        if step["name"] == "Upload Windows smoke diagnostics"
    )
    for phase in ("disk-full", "database-lock"):
        assert f"windows-{phase}-stdout.txt" in diagnostics["with"]["path"]
        assert f"windows-{phase}-stderr.txt" in diagnostics["with"]["path"]
