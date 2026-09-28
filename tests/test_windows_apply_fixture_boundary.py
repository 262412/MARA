"""The default-folder probe must refuse ordinary users before touching a path."""

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
