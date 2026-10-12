"""The default-folder probe must refuse ordinary users before touching a path."""

import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import windows_apply_fixture as fixture


@pytest.mark.parametrize(
    "variable,value",
    [
        ("GITHUB_ACTIONS", "false"),
        ("RUNNER_ENVIRONMENT", "self-hosted"),
        ("RUNNER_OS", "Linux"),
        ("GITHUB_REPOSITORY", "different/repository"),
    ],
)
def test_default_path_requires_disposable_account(monkeypatch, variable, value):
    for key, initial in {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Windows",
        "GITHUB_REPOSITORY": "262412/MARA",
    }.items():
        monkeypatch.setenv(key, initial)
    monkeypatch.setenv(variable, value)
    monkeypatch.setattr(fixture, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(fixture.getpass, "getuser", lambda: "runneradmin")

    def refuse_path(*args):
        raise AssertionError("A path was examined before rejecting the host")

    monkeypatch.setattr(fixture, "Path", refuse_path)
    with pytest.raises(RuntimeError, match="disposable hosted account"):
        fixture.hosted_scope()


def test_default_path_rejects_real_local_account(monkeypatch):
    monkeypatch.setattr(fixture.getpass, "getuser", lambda: "local-user")
    with pytest.raises(RuntimeError, match="disposable hosted account"):
        fixture.hosted_scope()


def test_inactive_console_guard_does_not_resolve_known_folder(monkeypatch):
    monkeypatch.delenv("MARA_CI_DEFAULT_APPLY_CHILD", raising=False)

    def forbidden():
        raise AssertionError("Inactive console guard touched a Known Folder")

    monkeypatch.setattr(fixture, "hosted_scope", forbidden)
    fixture.activate_console_guard()


@pytest.fixture
def owned_collection(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    contract = importlib.import_module("windows_default_apply_contract")
    root = tmp_path / "fake-known-folder"
    root.mkdir()
    runner = tmp_path / "runner"
    runner.mkdir()
    monkeypatch.setenv("GITHUB_SHA", "owned-sha")
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    monkeypatch.setattr(contract, "hosted_scope", lambda: (root, {}))
    (root / ".mara-pytest-owner").write_text("owned-token")
    (root / "authorization.json").write_text(
        json.dumps({"root": str(root), "sha": "owned-sha", "owner": "owned-token"})
    )
    return contract, root, runner / "collected"


@pytest.mark.parametrize("closed", [False, True])
def test_collection_preserves_scope_while_producer_is_live(owned_collection, closed):
    contract, root, destination = owned_collection
    (root / "producer-prepare.json").write_text(
        json.dumps({"pid": os.getpid(), "closed": closed})
    )
    with pytest.raises(RuntimeError, match="producer has not finished"):
        contract.collect(destination)
    assert root.is_dir() and destination.is_dir()


def test_collection_rejects_changed_owner_before_copying(owned_collection):
    contract, root, destination = owned_collection
    (root / ".mara-pytest-owner").write_text("different-owner")
    with pytest.raises(RuntimeError, match="authorization"):
        contract.collect(destination)
    assert root.is_dir() and not destination.exists()


def test_completed_owned_scope_is_collected_and_removed(owned_collection):
    contract, root, destination = owned_collection
    contract.collect(destination)
    assert not root.exists()
    assert json.loads((destination / "scope-cleanup.json").read_text()) == {
        "default_scope_removed": True
    }
