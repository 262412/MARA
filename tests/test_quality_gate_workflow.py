from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from scripts.supply_chain_pins import (
    APPROVED_WORKFLOW_JOB_RUNNERS,
    DEFAULT_GITHUB_RUNNER,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "quality-gates.yaml"
SIGNED_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "signed-provenance.yaml"
DESKTOP_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "desktop-gate2.yaml"
REQUIRED_JOBS = {
    "static",
    "dependency-audit",
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
    assert "uv lock --project docker --check" in static_commands
    assert "check_container_lock_parity.py" in static_commands
    assert "pre-commit run" in static_commands and "--all-files" in static_commands
    assert "check_codebase_hygiene.py" in static_commands
    assert "check_hygiene_baseline.py" in static_commands
    assert "check_supply_chain_policy.py" in static_commands
    assert "ruff check" in static_commands
    audit = jobs["dependency-audit"]
    assert audit["strategy"]["fail-fast"] is False
    assert audit["strategy"]["max-parallel"] == 1
    assert audit["strategy"]["matrix"]["include"] == [
        {"label": "root-py310", "project": ".", "python-version": "3.10"},
        {"label": "root-py311", "project": ".", "python-version": "3.11"},
        {
            "label": "container-py310",
            "project": "docker",
            "python-version": "3.10",
        },
    ]
    audit_commands = _commands(audit)
    assert "check_dependency_audit.py" in audit_commands
    assert "--project" in audit_commands
    assert "--python-version" in audit_commands
    audit_setup = next(
        step
        for step in audit["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    )
    assert audit_setup["with"]["python-version"] == "3.10"
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
    for job_name in ("benchmark-root", "coverage"):
        sync = next(
            step
            for step in jobs[job_name]["steps"]
            if step["name"] == "Sync locked environment"
        )
        assert "--all-packages" in sync["run"]


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
    assert "attest-build-provenance@" not in container_source
    assert "permissions" not in container
    build_step = next(step for step in container["steps"] if step.get("id") == "build")
    assert build_step["with"]["no-cache"] is True
    assert build_step["with"]["outputs"].strip().startswith("type=oci,")
    assert "type=docker" not in build_step["with"]["outputs"]
    container_commands = _commands(container)
    assert "skopeo copy" in container_commands
    assert "docker-daemon:" in container_commands
    assert "smoke_container_runtime.py" in container_commands
    assert 'print("Aa1!" + base64.urlsafe_b64encode' in container_commands
    expected_image_ref = "mara-quality:${{ matrix.target }}-${{ github.sha }}"
    trivy_steps = [
        step
        for step in container["steps"]
        if "aquasecurity/trivy-action@" in step.get("uses", "")
    ]
    assert len(trivy_steps) == 3
    for step in trivy_steps:
        assert step["with"]["image-ref"] == expected_image_ref
        assert "input" not in step["with"]
        assert step["with"]["timeout"] == "15m"
    vulnerability_scan = next(
        step
        for step in trivy_steps
        if step["name"] == "Scan fixable high and critical image findings"
    )
    assert vulnerability_scan["with"]["exit-code"] == "0"
    assert vulnerability_scan["with"]["format"] == "json"
    assert vulnerability_scan["with"]["output"].endswith(".trivy.json")
    assert "check_container_vulnerability_baseline.py" in container_commands
    assert "container_vulnerability_baseline.json" in container_commands
    assert "trivyignore" not in container_source.lower()

    python_commands = _commands(python)
    assert "publish_packages.py check" in python_commands
    assert "generate_distribution_attestations.py" in python_commands
    assert "upload-artifact@" in str(python)
    assert "attest-build-provenance@" not in str(python)
    assert "permissions" not in python


def test_signed_provenance_runs_only_after_a_successful_trusted_push():
    workflow = _load_workflow(SIGNED_WORKFLOW_PATH)
    triggers = _trigger(workflow)
    source = SIGNED_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert triggers == {
        "workflow_run": {
            "workflows": ["Quality gates"],
            "types": ["completed"],
            "branches": ["main", "Dev"],
        }
    }
    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    for job in workflow["jobs"].values():
        assert "workflow_run.conclusion == 'success'" in job["if"]
        assert "workflow_run.event == 'push'" in job["if"]
    assert "run-id: ${{ github.event.workflow_run.id }}" in source
    assert source.count("actions/attest-build-provenance@") == 2
    assert "subject-digest: ${{ steps.subject.outputs.digest }}" in source


def test_every_workflow_uses_immutable_actions_and_runner_images():
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
        workflow = _load_workflow(path)
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        for job_name, job in workflow.get("jobs", {}).items():
            runner = job.get("runs-on")
            if runner is not None:
                expected = APPROVED_WORKFLOW_JOB_RUNNERS.get(
                    (relative_path, job_name),
                    DEFAULT_GITHUB_RUNNER,
                )
                assert runner == expected, (path.name, job_name, runner)
            for step in job.get("steps", []):
                action = step.get("uses")
                if not action or action.startswith("./"):
                    continue
                assert FULL_SHA.fullmatch(action.rsplit("@", 1)[-1]), (
                    path.name,
                    action,
                )


def test_desktop_job_environment_uses_contexts_available_before_dispatch():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)

    for job in workflow["jobs"].values():
        for value in job.get("env", {}).values():
            assert "${{ runner." not in str(value)


def test_ubuntu_24_desktop_smoke_configures_the_electron_sandbox():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    job = workflow["jobs"]["smoke-linux-24"]
    commands = _commands(job)

    assert (
        "sudo chown root:root desktop-artifact/MARA-linux-x64/chrome-sandbox"
        in commands
    )
    assert "sudo chmod 4755 desktop-artifact/MARA-linux-x64/chrome-sandbox" in commands
    assert "--no-sandbox" not in commands


def test_windows_desktop_scan_removes_the_hosted_runner_drive_exclusion():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    job = workflow["jobs"]["package-windows"]
    scan = next(
        step
        for step in job["steps"]
        if step["name"] == "Scan package with Windows Defender"
    )
    commands = scan["run"]

    assert "(Resolve-Path" in commands
    assert "AntivirusEnabled" in commands
    assert "Remove-MpPreference -ExclusionPath $driveRoot" in commands
    assert "Set-MpPreference -DisableArchiveScanning $false" in commands
    assert "Start-MpScan" in commands and "-ErrorAction Stop" in commands
    assert "Get-MpThreatDetection" in commands


def test_desktop_jobs_smoke_deterministic_nonempty_data():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    jobs = workflow["jobs"]
    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "sidecar.smoke_fixture" in commands
        assert "--smoke-test-nonempty" in commands
        assert "--smoke-test-gate3-formats" in commands
        assert "--failure-marker" in commands
        assert "--smoke-test-gate3-model-unavailable" in commands
        assert "--smoke-test-gate3-retry" in commands

    linux_24_commands = _commands(jobs["smoke-linux-24"])
    assert "gate2-smoke-data" in linux_24_commands
    assert "--smoke-test-nonempty" in linux_24_commands
    assert "--smoke-test-gate3-formats" in linux_24_commands


def test_desktop_smoke_proves_cli_data_compatibility_without_retaining_paths():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    jobs = workflow["jobs"]
    linux_commands = _commands(jobs["package-linux-22"])
    windows = jobs["package-windows"]
    windows_commands = _commands(windows)

    assert ".venv/bin/MARA docqa index" in linux_commands
    assert linux_commands.count("MARA docqa files --json") == 3
    assert "--expect-name gate3-cli-compat.txt" in linux_commands
    assert "--expect-empty" in linux_commands
    assert "KH_APP_DATA_DIR" in linux_commands

    assert '".venv/Scripts/MARA.exe" docqa files --json' in windows_commands
    assert "--expect-name gate2-smoke.txt" in windows_commands
    assert "--expect-empty" in windows_commands
    diagnostics = next(
        step
        for step in windows["steps"]
        if step["name"] == "Upload Windows smoke diagnostics"
    )
    diagnostic_paths = diagnostics["with"]["path"]
    assert "windows-cli-compat-before.txt" in diagnostic_paths
    assert "windows-cli-compat-after.txt" in diagnostic_paths
    assert "cli_compatibility_probe.py" in linux_commands
    assert "cli_compatibility_probe.py" in windows_commands


def test_windows_smoke_seeds_the_same_system_appdata_used_by_electron():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    job = workflow["jobs"]["package-windows"]
    commands = _commands(job)

    assert "[Environment+SpecialFolder]::ApplicationData" in commands
    assert '$dataRoot = Join-Path $appData "MARA"' in commands
    assert "--data-root $dataRoot" in commands
    assert 'Join-Path $env:RUNNER_TEMP "mara-desktop-appdata"' not in commands


def test_linux_desktop_uploads_a_small_metrics_artifact():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    steps = workflow["jobs"]["package-linux-22"]["steps"]
    smoke = next(
        step
        for step in steps
        if step["name"] == "Smoke packaged vertical slice and record metrics"
    )
    metrics = next(
        step for step in steps if step["name"] == "Upload Ubuntu 22.04 metrics"
    )

    assert "linux-22-sidecar-sha256.txt" in smoke["run"]
    assert metrics["with"]["name"] == "mara-desktop-linux-22-metrics"
    assert metrics["with"]["path"] == "apps/desktop/release/metrics/"
    assert "MARA-linux-x64" not in metrics["with"]["path"]


def test_windows_defender_failure_uploads_diagnostics_but_not_the_package():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    steps = workflow["jobs"]["package-windows"]["steps"]
    diagnostics = next(
        step for step in steps if step["name"] == "Upload Windows Defender diagnostics"
    )
    package = next(
        step for step in steps if step["name"] == "Upload Windows package evidence"
    )

    assert diagnostics["if"] == "${{ always() }}"
    assert diagnostics["with"]["path"] == "apps/desktop/release/windows-defender.txt"
    assert package.get("if", "${{ success() }}") == "${{ success() }}"
    assert "MARA-win32-x64" in package["with"]["path"]
    assert "windows-defender.txt" not in package["with"]["path"]


def test_windows_packaged_smoke_always_uploads_process_diagnostics():
    workflow = _load_workflow(DESKTOP_WORKFLOW_PATH)
    steps = workflow["jobs"]["package-windows"]["steps"]
    smoke = next(
        step
        for step in steps
        if step["name"] == "Smoke packaged vertical slice and record metrics"
    )
    diagnostics = next(
        step for step in steps if step["name"] == "Upload Windows smoke diagnostics"
    )

    assert "-RedirectStandardOutput $stdout" in smoke["run"]
    assert "-RedirectStandardError $stderr" in smoke["run"]
    assert '"exit_code=$($process.ExitCode)"' in smoke["run"]
    assert diagnostics["if"] == "${{ always() }}"
    assert "windows-smoke-diagnostics.txt" in diagnostics["with"]["path"]
    assert "windows-smoke-stdout.txt" in diagnostics["with"]["path"]
    assert "windows-smoke-stderr.txt" in diagnostics["with"]["path"]
    assert "windows-fault-stdout.txt" in diagnostics["with"]["path"]
    assert "windows-fault-stderr.txt" in diagnostics["with"]["path"]
    assert "windows-retry-stdout.txt" in diagnostics["with"]["path"]
    assert "windows-retry-stderr.txt" in diagnostics["with"]["path"]
    assert "windows-metrics.txt" in diagnostics["with"]["path"]
    assert "MARA-win32-x64" not in diagnostics["with"]["path"]
    assert "sidecar_sha256=$sidecarSha256" in smoke["run"]


def test_workflows_do_not_grant_blanket_write_permissions():
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
        assert "write-all" not in path.read_text(encoding="utf-8"), path.name


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


def test_python_publish_reuses_the_digest_verified_quality_artifacts():
    quality = _load_workflow(WORKFLOW_PATH)["jobs"]["python-supply-chain"]
    upload = next(
        step
        for step in quality["steps"]
        if step.get("name") == "Upload distribution evidence"
    )
    assert "dist/supply-chain/" in upload["with"]["path"]
    assert "distribution-evidence/" in upload["with"]["path"]

    publish = _load_workflow(
        REPO_ROOT / ".github" / "workflows" / "publish-packages.yaml"
    )["jobs"]["publish"]
    assert "env" not in publish
    source = str(publish)
    commands = _commands(publish)
    assert "actions/download-artifact@" in source
    assert "generate_distribution_attestations.py" in commands
    assert "--verify" in commands
    assert "publish_packages.py" in commands
    assert "upload --outdir release-artifacts/dist/supply-chain" in commands
    assert 'publish_packages.py "${ARGS[@]}"' in commands
    assert "actions/attest-build-provenance@" in source
    assert publish["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }


def test_release_container_digest_is_signed_and_pushed_to_the_registry():
    build = _load_workflow(
        REPO_ROOT / ".github" / "workflows" / "build-push-docker.yaml"
    )["jobs"]["build"]
    attest = next(
        step
        for step in build["steps"]
        if str(step.get("uses", "")).startswith("actions/attest-build-provenance@")
    )

    assert attest["with"]["subject-digest"] == "${{ steps.build.outputs.digest }}"
    assert attest["with"]["push-to-registry"] is True


def test_supply_chain_pin_changes_require_trusted_context_owner_review():
    path = REPO_ROOT / ".github" / "workflows" / "supply-chain-review.yaml"
    workflow = _load_workflow(path)
    triggers = _trigger(workflow)
    source = path.read_text(encoding="utf-8")

    assert "pull_request_target" in triggers
    assert triggers["pull_request_review"]["types"] == ["submitted", "dismissed"]
    assert "pull_request" not in triggers
    assert "actions/checkout@" not in source
    assert "pull_request.head.sha" in source
    assert "author_association" in source
    assert "APPROVED" in source
    assert "COLLABORATOR" in source
    assert "pull_request.changed_files" in source
    assert "len(files) != expected_file_count" in source
    for protected in (
        ".dockerignore",
        ".gitleaks",
        "gitleaks.toml",
        ".trivy",
        "trivy.yaml",
        "trivy.yml",
        "pyproject.toml",
        "uv.lock",
        "constraints.txt",
        "requirements.txt",
        "requirements.azure.in",
        "package-lock.json",
        "install.sh",
        "install.ps1",
        "publish_packages.py",
        "MANIFEST.in",
        "generate_distribution_attestations.py",
        "generate_container_attestation.py",
        "smoke_container_runtime.py",
        "check_container_lock_parity.py",
        "check_dependency_audit.py",
        "dependency_audit_baseline.json",
    ):
        assert protected in source
    assert "two-person control" in source


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
