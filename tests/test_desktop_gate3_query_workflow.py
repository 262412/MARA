from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_linux_cross_version_smoke_reuses_the_persisted_model_endpoint() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "smoke-linux-24"):
        commands = _commands(jobs[job_name])
        assert "smoke_model_port=43127" in commands
        assert '--port "$smoke_model_port"' in commands


def test_native_packages_capture_the_saved_model_and_scrub_route_secrets() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "smoke_model_route_fixture" in commands
        assert "settings-chat-route.json" in commands
        assert "gpt-5.6-luna" in commands
        assert "MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS" in commands

    windows_commands = _commands(jobs["package-windows"])
    assert "--smoke-test-model-settings-secure" in windows_commands
    assert "state/model-credentials.bin" in windows_commands
    assert (
        "--forbidden-secret mara-desktop-settings-secret-sentinel" in windows_commands
    )


def test_desktop_route_implementation_changes_trigger_native_packages() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    expected_paths = {
        "libs/ktem/ktem/desktop_model_routes.py",
        "libs/ktem/ktem/embeddings/**",
        "libs/ktem/ktem/llms/**",
        "libs/ktem/ktem_tests/test_desktop_model_routes.py",
        "libs/ktem/ktem_tests/test_model_managers.py",
    }

    for event in ("pull_request", "push"):
        paths = set(workflow["on"][event]["paths"])
        assert expected_paths <= paths


def test_windows_diagnostics_retain_actual_route_and_migration_reports() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["package-windows"]["steps"]
    upload = next(
        step for step in steps if step.get("name") == "Upload Windows smoke diagnostics"
    )
    uploaded_paths = upload["with"]["path"]

    assert "windows-settings-chat-route.json" in uploaded_paths
    assert "windows-model-route-migration.json" in uploaded_paths
