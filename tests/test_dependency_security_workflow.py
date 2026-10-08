import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/quality-gates.yaml"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load_workflow(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _trigger(workflow):
    return workflow.get("on", workflow.get(True, {}))


def _commands(job):
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_storage_and_nltk_remediation_are_required_on_supported_platforms():
    jobs = _load_workflow(WORKFLOW_PATH)["jobs"]
    for name in ("kotaemon", "windows-storage-security"):
        commands = _commands(jobs[name])
        assert "check_nltk_backport.py --advisories --tests" in commands
        assert "--with chromadb==0.5.17" in commands
        assert "test_legacy_snapshot_export_import_and_source_rollback" in commands
    windows = jobs["windows-storage-security"]
    assert windows["runs-on"] == "windows-2022"
    assert "test_nltk_path_security.py" in _commands(windows)
    assert "test_qdrant_local.py" in _commands(windows)
    assert "test_qdrant_service.py" in _commands(windows)
    assert "test_source_write_processes.py" in _commands(windows)
    assert "windows-storage-security" in jobs["required"]["needs"]
    for name in (
        "kotaemon",
        "windows-storage-security",
        "ktem",
        "slide-cli",
        "coverage",
        "wheel-smoke",
        "frontend-browser",
        "container-supply-chain",
    ):
        assert "prepare_qdrant_test_service.py" in _commands(jobs[name])


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
