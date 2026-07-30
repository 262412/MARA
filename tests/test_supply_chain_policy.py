from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from scripts.check_supply_chain_policy import (
    _check_action_pins,
    _check_runners,
    scan_repository,
)
from scripts.supply_chain_pins import APPROVED_ACTIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_INSTALLERS = (
    "scripts/run_linux.sh",
    "scripts/run_macos.sh",
    "scripts/run_windows.bat",
    "scripts/setup.sh",
    "scripts/setup.ps1",
    "scripts/update_linux.sh",
    "scripts/update_macos.sh",
    "scripts/update_windows.bat",
)


def test_repository_satisfies_supply_chain_policy():
    assert scan_repository(REPO_ROOT) == []


def test_runtime_dependencies_exclude_llama_hub_secret_bearing_examples():
    pyproject = tomllib.loads(
        (REPO_ROOT / "libs/kotaemon/pyproject.toml").read_text(encoding="utf-8")
    )

    assert all(
        not dependency.startswith("llama-hub")
        for dependency in pyproject["project"]["dependencies"]
    )


def test_supply_chain_policy_cli_is_fail_closed():
    completed = subprocess.run(
        [sys.executable, "scripts/check_supply_chain_policy.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "Supply-chain policy passed."


def test_canonical_installers_use_only_the_frozen_source_lock():
    for relative in ("install.sh", "install.ps1"):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "uv sync" in source
        assert "--frozen" in source
        assert "--no-dev" in source
        assert "pip install" not in source
        assert "mara-app[mara]" not in source


def test_legacy_installers_are_formally_retired_and_fail_closed():
    for relative in LEGACY_INSTALLERS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "retired" in source.lower(), relative
        assert "install.sh" in source or "install.ps1" in source, relative
        if relative.endswith((".bat", ".ps1")):
            assert "exit" in source.lower() and "64" in source, relative
        else:
            assert "exit 64" in source, relative


def test_action_policy_rejects_unknown_digests_and_malformed_version_comments():
    unknown = (
        "steps:\n"
        "  - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        " # v4.2.2\n"
    )
    malformed = (
        "steps:\n"
        "  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
        " # release-4\n"
    )

    unknown_rules = {
        item.rule for item in _check_action_pins(Path("test.yml"), unknown)
    }
    malformed_rules = {
        item.rule for item in _check_action_pins(Path("test.yml"), malformed)
    }

    assert "action-allowlist" in unknown_rules
    assert "action-version-comment" in malformed_rules


def test_desktop_runner_exceptions_are_limited_to_the_required_jobs():
    path = Path(".github/workflows/desktop-gate2.yaml")
    source = """
jobs:
  package-linux-22:
    runs-on: ubuntu-22.04
  smoke-linux-24:
    runs-on: ubuntu-24.04
  package-windows:
    runs-on: windows-2022
"""
    workflow = yaml.safe_load(source)

    assert _check_runners(path, source, workflow) == []

    workflow["jobs"]["smoke-linux-24"]["runs-on"] = "windows-2022"
    violations = _check_runners(path, source, workflow)
    assert [(item.rule, item.detail) for item in violations] == [
        (
            "runner-pin",
            "job 'smoke-linux-24' runner is 'windows-2022'; expected 'ubuntu-24.04'",
        )
    ]


def test_setup_node_pin_is_independently_registered():
    assert (
        APPROVED_ACTIONS["actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020"]
        == "v4.4.0"
    )


def test_external_precommit_revisions_are_full_verified_commits():
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    for repository in config["repos"]:
        if repository["repo"] == "local":
            continue
        assert len(repository["rev"]) == 40
        int(repository["rev"], 16)


def test_dockerfile_frontend_is_digest_pinned():
    first_line = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()[0]
    assert first_line == (
        "# syntax=docker/dockerfile:1.7@"
        "sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e"
    )


def test_setup_uv_downloads_are_versioned_and_checksum_verified():
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                if not str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                    continue
                assert step["with"]["version"] == "0.11.19"
                assert step["with"]["checksum"] == (
                    "7035608168e106375b36d0c818d537a889c51a8625fe7f8f7cad5e62b947c368"
                )


def test_buildx_and_buildkit_are_version_and_digest_pinned():
    for path in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                if not str(step.get("uses", "")).startswith(
                    "docker/setup-buildx-action@"
                ):
                    continue
                assert step["with"] == {
                    "version": "v0.34.1",
                    "driver-opts": (
                        "image=moby/buildkit:v0.30.0@sha256:"
                        "0168606be2315b7c807a03b3d8aa79beefdb31c98740cebdffdfeebf31190c9f"
                    ),
                }
