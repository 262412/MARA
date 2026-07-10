import os
import subprocess
import sys

import click
import pytest
from click.testing import CliRunner

from kotaemon import app_init as app_init_module
from kotaemon import cli as cli_module


def _package_mode_env(tmp_path, *, overrides=None):
    env = os.environ.copy()
    env.pop("THEFLOW_SETTINGS_MODULE", None)
    env.pop("KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED", None)
    env.pop("MARA_ADMIN_PASSWORD_FILE", None)
    env.pop("MARA_AUTH_MODE", None)
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "USERPROFILE": str(tmp_path / "home"),
            "APPDATA": str(tmp_path / "config"),
            "LOCALAPPDATA": str(tmp_path / "data"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "MARA_RUNTIME_DIR": str(tmp_path / "runtime"),
            "KH_APP_DATA_DIR": str(tmp_path / "runtime" / "ktem_app_data"),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    env.update(overrides or {})
    return env


def _run_package_mode_cli(tmp_path, *args, env_overrides=None):
    return subprocess.run(
        [sys.executable, "-m", "kotaemon.cli", *args],
        cwd=str(tmp_path),
        env=_package_mode_env(tmp_path, overrides=env_overrides),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _config_file_paths(tmp_path):
    config_dir = tmp_path / "config" / "Kotaemon"
    return (
        config_dir / "flowsettings.py",
        config_dir / ".env",
        config_dir / ".env.example",
    )


def _seed_config_files(tmp_path):
    snapshots = {}
    for index, path in enumerate(_config_file_paths(tmp_path)):
        path.parent.mkdir(parents=True, exist_ok=True)
        contents = f"# original-config-{index}\n".encode()
        path.write_bytes(contents)
        snapshots[path] = contents
    return snapshots


def _assert_config_snapshot(snapshots):
    for path, contents in snapshots.items():
        if contents is None:
            assert not path.exists()
        else:
            assert path.read_bytes() == contents


@pytest.mark.parametrize(
    ("admin_user", "password", "error_fragment"),
    [
        ("   ", "CorrectHorse7!", "username must be nonempty"),
        ("Operator", "weak-secret", "uppercase"),
    ],
)
def test_app_init_policy_failure_preserves_existing_config_bytes(
    tmp_path,
    admin_user,
    password,
    error_fragment,
):
    snapshots = _seed_config_files(tmp_path)
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text(password, encoding="utf-8")

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--auth-mode",
        "password",
        "--admin-user",
        admin_user,
        env_overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
    )

    assert result.returncode != 0
    assert error_fragment in result.stdout + result.stderr
    _assert_config_snapshot(snapshots)


@pytest.mark.parametrize("seed_existing", [False, True], ids=["absent", "existing"])
@pytest.mark.parametrize("failure_kind", ["hash", "database"])
def test_app_init_provision_failure_restores_config_and_hides_db_secrets(
    monkeypatch,
    tmp_path,
    seed_existing,
    failure_kind,
):
    snapshots = (
        _seed_config_files(tmp_path)
        if seed_existing
        else {path: None for path in _config_file_paths(tmp_path)}
    )
    password = "RollbackHorse7!"
    stored_hash = "$mara-bcrypt-sha256$synthetic-stored-hash"
    password_path = tmp_path / "private-admin-location.txt"
    password_path.write_text(password, encoding="utf-8")
    env = _package_mode_env(
        tmp_path,
        overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
    )
    monkeypatch.setattr(
        app_init_module,
        "preflight_password_admin",
        lambda **_kwargs: None,
    )

    def _fail_provision(**_kwargs):
        if failure_kind == "hash":
            raise RuntimeError("synthetic hash failure")
        raise click.ClickException("Password administrator database operation failed.")

    monkeypatch.setattr(app_init_module, "provision_password_admin", _fail_provision)

    result = CliRunner().invoke(
        cli_module.app,
        ["init", "--force", "--auth-mode", "password"],
        env=env,
    )

    assert result.exit_code != 0
    _assert_config_snapshot(snapshots)
    assert password not in result.output
    assert stored_hash not in result.output
    assert str(password_path) not in result.output


def test_app_init_existing_user_without_force_preflights_before_config_write(tmp_path):
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text("OriginalHorse7!", encoding="utf-8")
    env_overrides = {"MARA_ADMIN_PASSWORD_FILE": str(password_path)}
    created = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        env_overrides=env_overrides,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    snapshots = _seed_config_files(tmp_path)
    password_path.write_text("ReplacementHorse8!", encoding="utf-8")

    refused = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--auth-mode",
        "password",
        env_overrides=env_overrides,
    )

    assert refused.returncode != 0
    assert "already exists" in refused.stdout + refused.stderr
    assert "--force" in refused.stdout + refused.stderr
    _assert_config_snapshot(snapshots)
