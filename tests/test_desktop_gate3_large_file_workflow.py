from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_native_package_jobs_measure_the_large_file_canary() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        assert "--smoke-test-gate3-large-file" in _commands(jobs[job_name])

    linux_commands = _commands(jobs["package-linux-22"])
    assert "linux-22-large-file-time.txt" in linux_commands
    assert "--phase large-file-recovered" in linux_commands

    windows = jobs["package-windows"]
    windows_commands = _commands(windows)
    assert '"large_file_exit_code=$($largeFileProcess.ExitCode)"' in windows_commands
    assert '"large_file_elapsed_ms=$($largeFileStopwatch.ElapsedMilliseconds)"' in (
        windows_commands
    )
    assert '"large_file_peak_working_set_bytes=$largeFilePeakWorkingSet"' in (
        windows_commands
    )
    diagnostics = next(
        step
        for step in windows["steps"]
        if step["name"] == "Upload Windows smoke diagnostics"
    )
    assert "windows-large-file-stdout.txt" in diagnostics["with"]["path"]
    assert "windows-large-file-stderr.txt" in diagnostics["with"]["path"]
