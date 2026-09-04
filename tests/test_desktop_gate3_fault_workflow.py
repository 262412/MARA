from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_native_package_jobs_prove_partial_failure_and_targeted_retry() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "--smoke-test-gate3-partial" in commands

    linux_commands = _commands(jobs["package-linux-22"])
    assert "linux-22-partial-stdout.txt" in linux_commands
    assert "--phase partial-recovered" in linux_commands

    windows = jobs["package-windows"]
    windows_commands = _commands(windows)
    assert '"partial_exit_code=$($partialProcess.ExitCode)"' in windows_commands
    diagnostics = next(
        step
        for step in windows["steps"]
        if step["name"] == "Upload Windows smoke diagnostics"
    )
    assert "windows-partial-stdout.txt" in diagnostics["with"]["path"]
    assert "windows-partial-stderr.txt" in diagnostics["with"]["path"]
