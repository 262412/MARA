from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "quality-gates.yaml"
REQUIRED_JOBS = {
    "static",
    "collection",
    "secret-scan",
    "kotaemon",
    "ktem",
    "slide-cli",
    "benchmark-root",
    "frontend-browser",
    "coverage",
    "wheel-smoke",
    "container-supply-chain",
    "python-supply-chain",
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
    collection_commands = _commands(jobs["collection"])
    assert "check_pytest_collection.py" in collection_commands
    assert "--minimum 1260" in collection_commands
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
    assert "./node_modules/.bin/playwright" in frontend_commands
    assert "npx" not in frontend_commands
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


def test_supply_chain_jobs_build_scan_and_retain_evidence():
    jobs = _load_workflow(WORKFLOW_PATH)["jobs"]
    container = jobs["container-supply-chain"]
    python = jobs["python-supply-chain"]

    assert container["strategy"]["matrix"]["target"] == ["lite", "full", "ollama"]
    container_source = str(container)
    for token in (
        "docker/build-push-action@",
        "aquasecurity/trivy-action@",
        "vuln,secret,misconfig",
        "HIGH,CRITICAL",
        "sbom",
        "provenance",
        "spdx-json",
        "cyclonedx",
        "upload-artifact@",
    ):
        assert token in container_source

    python_commands = _commands(python)
    assert "publish_packages.py check" in python_commands
    assert "generate_distribution_attestations.py" in python_commands
    assert "upload-artifact@" in str(python)


def test_every_workflow_uses_immutable_actions_and_runner_images():
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
        workflow = _load_workflow(path)
        for job in workflow.get("jobs", {}).values():
            runner = job.get("runs-on")
            if runner is not None:
                assert runner == "ubuntu-24.04", (path.name, runner)
            for step in job.get("steps", []):
                action = step.get("uses")
                if not action or action.startswith("./"):
                    continue
                assert FULL_SHA.fullmatch(action.rsplit("@", 1)[-1]), (
                    path.name,
                    action,
                )


def test_release_workflows_have_no_mutable_latest_aliases():
    for name in (
        "auto-bump-and-release.yaml",
        "build-push-docker.yaml",
        "publish-packages.yaml",
    ):
        source = (REPO_ROOT / ".github" / "workflows" / name).read_text(
            encoding="utf-8"
        )
        assert "make_latest:" not in source
        assert "refs/heads/latest" not in source
        assert "type=raw,value=latest" not in source


@pytest.mark.parametrize(
    ("path", "publish_job", "trusted_base"),
    [
        ("publish-packages.yaml", "publish", "main"),
        ("build-push-docker.yaml", "build", "main"),
        (
            "auto-bump-and-release.yaml",
            "auto-bump-and-release",
            "${{ github.event.before }}",
        ),
    ],
)
def test_release_workflows_are_frozen_behind_reusable_quality_gate(
    path, publish_job, trusted_base
):
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / path)
    jobs = workflow["jobs"]

    assert jobs["quality"]["uses"] == "./.github/workflows/quality-gates.yaml"
    assert jobs["quality"]["with"]["base_ref"] == trusted_base
    assert jobs[publish_job]["needs"] == "quality"
    assert jobs[publish_job]["if"] == "${{ false }}"


def test_non_pr_quality_calls_use_a_trusted_base_not_head_parent():
    workflow = _load_workflow(WORKFLOW_PATH)
    triggers = _trigger(workflow)
    source = WORKFLOW_PATH.read_text(encoding="utf-8")

    base_input = triggers["workflow_call"]["inputs"]["base_ref"]
    assert base_input["type"] == "string"
    assert base_input["required"] is False
    assert "HEAD^" not in source
    for job_name in ("static", "coverage"):
        base_expression = workflow["jobs"][job_name]["env"]["MARA_BASE_REF"]
        assert "inputs.base_ref" in base_expression
        assert "github.event.pull_request.base.sha" in base_expression
        assert "github.event.before" in base_expression
        assert "github.event.repository.default_branch" in base_expression


def test_secret_scan_is_reusable_required_and_pinned():
    quality = _load_workflow(WORKFLOW_PATH)
    secret_path = REPO_ROOT / ".github" / "workflows" / "secret-scan.yaml"
    secret = _load_workflow(secret_path)
    triggers = _trigger(secret)

    assert quality["jobs"]["secret-scan"]["uses"] == (
        "./.github/workflows/secret-scan.yaml"
    )
    assert "secret-scan" in quality["jobs"]["required"]["needs"]
    assert "workflow_call" in triggers
    assert "pull_request" not in triggers
    assert "push" not in triggers
    for job in secret["jobs"].values():
        for step in job.get("steps", []):
            action = step.get("uses")
            if action and not action.startswith("./"):
                assert FULL_SHA.fullmatch(action.rsplit("@", 1)[-1]), action


@pytest.mark.parametrize("path", ["style-check.yaml", "unit-test.yaml"])
def test_superseded_workflows_no_longer_duplicate_branch_events(path):
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / path)
    triggers = _trigger(workflow)

    assert "pull_request" not in triggers
    assert "push" not in triggers
    assert set(triggers) <= {"workflow_dispatch", "workflow_call"}
