from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_native_packages_cover_read_only_cwd_and_unconfigured_first_start() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "--smoke-test-indexing-unconfigured" in commands
        assert "index-tasks.json" in commands
        assert ".theflow" in commands
        assert "cache/theflow" in commands or "cache\\theflow" in commands

    linux_commands = _commands(jobs["package-linux-22"])
    assert "cd /usr" in linux_commands
    assert "embedding_not_configured" in linux_commands

    windows_commands = _commands(jobs["package-windows"])
    assert "icacls" in windows_commands
    assert "/deny" in windows_commands
    assert "-WorkingDirectory $readOnlyCwd" in windows_commands
    assert "embedding_not_configured" in windows_commands


def test_desktop_workflow_tracks_embedding_and_storage_runtime_sources() -> None:
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '"libs/ktem/ktem/default_flowsettings.py"' in source
    assert '"libs/ktem/ktem/runtime_defaults.py"' in source
    assert '"libs/kotaemon/kotaemon/embeddings/**"' in source
