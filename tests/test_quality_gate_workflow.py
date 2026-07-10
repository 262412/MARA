from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "quality-gates.yaml"
REQUIRED_JOBS = {
    "static",
    "kotaemon",
    "ktem",
    "slide-cli",
    "benchmark-root",
    "frontend-browser",
    "coverage",
    "wheel-smoke",
    "required",
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _trigger(workflow: dict) -> dict:
    # PyYAML 1.1 treats the plain scalar ``on`` as a boolean.
    return workflow.get("on", workflow.get(True, {}))


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_quality_workflow_is_reusable_and_covers_main_and_dev():
    workflow = _load_workflow(WORKFLOW_PATH)
    triggers = _trigger(workflow)

    assert "workflow_call" in triggers
    for event in ("pull_request", "push"):
        assert set(triggers[event]["branches"]) == {"main", "Dev"}
    assert workflow["permissions"] == {"contents": "read"}
    assert REQUIRED_JOBS <= set(workflow["jobs"])


def test_quality_workflow_uses_pinned_external_actions_and_no_secrets():
    workflow = _load_workflow(WORKFLOW_PATH)
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "secrets." not in source
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            action = step.get("uses")
            if not action or action.startswith("./"):
                continue
            reference = action.rsplit("@", 1)[-1]
            assert FULL_SHA.fullmatch(reference), action


def test_static_and_test_jobs_enforce_the_repository_contracts():
    jobs = _load_workflow(WORKFLOW_PATH)["jobs"]
    static_commands = _commands(jobs["static"])

    assert "uv sync --frozen" in static_commands
    assert "uv lock --check" in static_commands
    assert "pre-commit run" in static_commands and "--all-files" in static_commands
    assert "check_codebase_hygiene.py" in static_commands
    assert "check_hygiene_baseline.py" in static_commands
    assert "ruff check" in static_commands
    assert jobs["kotaemon"]["strategy"]["matrix"]["python-version"] == [
        "3.10",
        "3.11",
    ]
    assert "libs/kotaemon" in _commands(jobs["kotaemon"])
    assert "libs/ktem/ktem_tests" in _commands(jobs["ktem"])
    assert "libs/slide_cli" in _commands(jobs["slide-cli"])
    root_commands = _commands(jobs["benchmark-root"])
    assert "benchmark/tests" in root_commands and "tests" in root_commands


def test_frontend_coverage_and_wheel_jobs_are_executable_gates():
    jobs = _load_workflow(WORKFLOW_PATH)["jobs"]
    frontend_commands = _commands(jobs["frontend-browser"])
    coverage_commands = _commands(jobs["coverage"])
    wheel_commands = _commands(jobs["wheel-smoke"])

    assert "node --test" in frontend_commands
    assert "playwright@" in frontend_commands
    assert "chromium" in frontend_commands
    assert "tests/browser" in frontend_commands
    assert "run_coverage_gates.py" in coverage_commands
    assert "check_diff_coverage.py" in coverage_commands
    assert "upload-artifact" in "\n".join(
        step.get("uses", "") for step in jobs["coverage"]["steps"]
    )
    assert "publish_packages.py" in wheel_commands
    assert "run_clean_wheel_smoke.py" in wheel_commands

    required = jobs["required"]
    assert set(required["needs"]) == REQUIRED_JOBS - {"required"}
    assert "always()" in required["if"]


@pytest.mark.parametrize(
    ("path", "publish_job"),
    [
        ("publish-packages.yaml", "publish"),
        ("build-push-docker.yaml", "build"),
        ("auto-bump-and-release.yaml", "auto-bump-and-release"),
    ],
)
def test_release_workflows_are_frozen_behind_reusable_quality_gate(path, publish_job):
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / path)
    jobs = workflow["jobs"]

    assert jobs["quality"]["uses"] == "./.github/workflows/quality-gates.yaml"
    assert jobs[publish_job]["needs"] == "quality"
    assert jobs[publish_job]["if"] == "${{ false }}"


@pytest.mark.parametrize("path", ["style-check.yaml", "unit-test.yaml"])
def test_superseded_workflows_no_longer_duplicate_branch_events(path):
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / path)
    triggers = _trigger(workflow)

    assert "pull_request" not in triggers
    assert "push" not in triggers
    assert set(triggers) <= {"workflow_dispatch", "workflow_call"}
