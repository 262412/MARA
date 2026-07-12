import hashlib
import os
import sqlite3
import subprocess
import sys

import click
import pytest
from click.testing import CliRunner
from ktem.auth.passwords import verify_password

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


def _create_user_database(database_path, *, username, password_hash, admin):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'CREATE TABLE "user" ('
            "id VARCHAR NOT NULL PRIMARY KEY, "
            "username VARCHAR NOT NULL UNIQUE, "
            "username_lower VARCHAR NOT NULL UNIQUE, "
            "password VARCHAR NOT NULL, admin BOOLEAN NOT NULL)"
        )
        connection.execute(
            'INSERT INTO "user" '
            "(id, username, username_lower, password, admin) VALUES (?, ?, ?, ?, ?)",
            ("trap-user", username, username.lower(), password_hash, int(admin)),
        )


def _read_user(database_path, username_lower):
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            'SELECT username, username_lower, password, admin FROM "user" '
            "WHERE username_lower = ?",
            (username_lower,),
        ).fetchone()


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


def test_app_init_force_ignores_existing_flowsettings_database_override(tmp_path):
    config_dir = tmp_path / "config" / "Kotaemon"
    config_dir.mkdir(parents=True)
    trap_database = tmp_path / "trap-runtime" / "sql.db"
    trap_hash = "trap-password-hash-must-remain-unchanged"
    _create_user_database(
        trap_database,
        username="admin",
        password_hash=trap_hash,
        admin=False,
    )
    before_hash = hashlib.sha256(trap_database.read_bytes()).hexdigest()
    (config_dir / "flowsettings.py").write_text(
        f"KH_DATABASE = {f'sqlite:///{trap_database}'!r}\n",
        encoding="utf-8",
    )
    password = "DefaultDatabaseHorse7!"
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text(password, encoding="utf-8")

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        env_overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert hashlib.sha256(trap_database.read_bytes()).hexdigest() == before_hash
    assert _read_user(trap_database, "admin") == ("admin", "admin", trap_hash, 0)
    default_database = tmp_path / "data" / "Kotaemon" / "user_data" / "sql.db"
    default_user = _read_user(default_database, "admin")
    assert default_user[:2] == ("admin", "admin")
    assert verify_password(password, default_user[2]) == (True, None)
    assert default_user[3] == 1


def test_admin_provisioning_import_does_not_load_runtime_database_modules(tmp_path):
    command = [
        sys.executable,
        "-c",
        (
            "import json, sys; import ktem.auth.admin_provisioning; "
            "print(json.dumps({name: name in sys.modules for name in "
            "['ktem.db.engine', 'ktem.db.models']}))"
        ),
    ]

    result = subprocess.run(
        command,
        cwd=str(tmp_path),
        env=_package_mode_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        '{"ktem.db.engine": false, "ktem.db.models": false}'
    )


def _seed_symlinked_env(tmp_path):
    snapshots = _seed_config_files(tmp_path)
    _flowsettings_path, env_path, _example_path = _config_file_paths(tmp_path)
    env_path.unlink()
    target_path = tmp_path / "linked-config" / "runtime.env"
    target_path.parent.mkdir(parents=True)
    original_contents = b"ORIGINAL_LINKED_ENV=value\n"
    target_path.write_bytes(original_contents)
    env_path.symlink_to(target_path)
    snapshots[env_path] = original_contents
    return env_path, target_path, original_contents, snapshots


def test_app_init_success_preserves_config_symlink_topology(tmp_path):
    env_path, target_path, _original_contents, _snapshots = _seed_symlinked_env(
        tmp_path
    )
    link_target = os.readlink(env_path)

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "local",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert env_path.is_symlink()
    assert os.readlink(env_path) == link_target
    assert "MARA_AUTH_MODE=local" in target_path.read_text(encoding="utf-8")


def test_app_init_rollback_preserves_config_symlink_topology(monkeypatch, tmp_path):
    env_path, target_path, original_contents, snapshots = _seed_symlinked_env(tmp_path)
    link_target = os.readlink(env_path)
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text("RollbackHorse7!", encoding="utf-8")
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
        raise RuntimeError("provision failed")

    monkeypatch.setattr(app_init_module, "provision_password_admin", _fail_provision)

    result = CliRunner().invoke(
        cli_module.app,
        ["init", "--force", "--auth-mode", "password"],
        env=env,
    )

    assert result.exit_code != 0
    assert env_path.is_symlink()
    assert os.readlink(env_path) == link_target
    assert target_path.read_bytes() == original_contents
    _assert_config_snapshot(snapshots)
