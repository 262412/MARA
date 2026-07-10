import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from ktem.auth.passwords import verify_password

from kotaemon import app_init as app_init_module
from kotaemon import cli as cli_module
from kotaemon.cli import _extract_json_payload


def _package_mode_env(tmp_path, *, overrides=None):
    home_dir = tmp_path / "home"
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    for path in (home_dir, config_dir, data_dir, cache_dir):
        path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop("THEFLOW_SETTINGS_MODULE", None)
    env.pop("KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED", None)
    env.pop("MARA_ADMIN_PASSWORD_FILE", None)
    env.pop("MARA_AUTH_MODE", None)
    env["HOME"] = str(home_dir)
    env["USERPROFILE"] = str(home_dir)
    env["APPDATA"] = str(config_dir)
    env["LOCALAPPDATA"] = str(data_dir)
    env["XDG_CONFIG_HOME"] = str(config_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["MARA_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["KH_APP_DATA_DIR"] = str(tmp_path / "runtime" / "ktem_app_data")
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(overrides or {})
    return env


def _run_package_mode_cli(tmp_path, *args, env_overrides=None, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "kotaemon.cli", *args],
        cwd=str(cwd or tmp_path),
        env=_package_mode_env(tmp_path, overrides=env_overrides),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_docqa_doctor_runs_outside_repo(tmp_path):
    result = _run_package_mode_cli(tmp_path, "docqa", "doctor", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert payload["ok"] is True
    assert payload["index_name"] == "File Collection"


def test_app_doctor_runs_outside_repo(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "doctor", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert payload["settings_source"] == "package-default"
    assert Path(payload["app_data_dir"]).exists()
    assert Path(payload["file_storage_path"]).exists()


def test_app_init_writes_user_config_files(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "init", "--force", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert Path(payload["config_dir"]).exists()
    assert Path(payload["flowsettings_path"]).exists()
    assert Path(payload["env_path"]).exists()
    assert Path(payload["env_example_path"]).exists()


def test_app_init_legacy_json_invocation_keeps_keys_and_defaults_to_auto(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "init", "--force", "--json")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    assert set(payload) == {
        "config_dir",
        "data_dir",
        "cache_dir",
        "flowsettings_path",
        "env_path",
        "env_example_path",
    }
    env_text = Path(payload["env_path"]).read_text(encoding="utf-8")
    example_text = Path(payload["env_example_path"]).read_text(encoding="utf-8")
    assert "MARA_AUTH_MODE=auto" in env_text
    assert "MARA_ADMIN_PASSWORD_FILE" not in env_text
    assert "MARA_AUTH_MODE=auto" in example_text
    assert "MARA_ADMIN_PASSWORD_FILE=" in example_text
    assert "Admin password" not in result.stdout + result.stderr


@pytest.mark.parametrize("auth_mode", ["auto", "local", "sso"])
def test_app_init_writes_selected_nonpassword_auth_mode(tmp_path, auth_mode):
    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        auth_mode,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    env_text = Path(payload["env_path"]).read_text(encoding="utf-8")
    assert f"MARA_AUTH_MODE={auth_mode}" in env_text
    assert "MARA_ADMIN_PASSWORD_FILE" not in env_text


def test_app_init_hidden_confirmation_prompt_never_echoes_password(monkeypatch):
    password = "PromptHorse7!"
    provisioned = []
    payload = {
        "config_dir": "/config",
        "data_dir": "/data",
        "cache_dir": "/cache",
        "flowsettings_path": "/config/flowsettings.py",
        "env_path": "/config/.env",
        "env_example_path": "/config/.env.example",
    }
    monkeypatch.delenv("MARA_ADMIN_PASSWORD_FILE", raising=False)
    monkeypatch.setattr(app_init_module, "is_interactive_terminal", lambda: True)

    def _initialize_password_app(**kwargs):
        provisioned.append(kwargs)
        return payload

    monkeypatch.setattr(
        cli_module,
        "_initialize_password_app",
        _initialize_password_app,
    )

    result = CliRunner().invoke(
        cli_module.app,
        ["init", "--auth-mode", "password", "--admin-user", "Operator"],
        input=f"{password}\n{password}\n",
    )

    assert result.exit_code == 0, result.output
    assert provisioned == [
        {"username": "Operator", "password": password, "force": False}
    ]
    assert password not in result.output
    assert "Admin password" in result.output
    assert "Repeat for confirmation" in result.output


@pytest.mark.parametrize(
    ("file_kind", "content", "error_fragment"),
    [
        ("missing", None, "existing regular file"),
        ("directory", None, "existing regular file"),
        ("fifo", None, "existing regular file"),
        ("file", b"", "nonempty line"),
        ("file", b"\n", "nonempty line"),
        ("file", b"CorrectHorse7!\nSecondHorse8!", "exactly one"),
        ("file", b"CorrectHorse7!\n\n", "exactly one"),
        ("file", b"\xff\xfe", "UTF-8"),
    ],
)
def test_app_init_rejects_invalid_password_file_without_leaking_path(
    tmp_path,
    file_kind,
    content,
    error_fragment,
):
    password_path = tmp_path / "admin-secret.txt"
    if file_kind == "directory":
        password_path.mkdir()
    elif file_kind == "fifo":
        os.mkfifo(password_path)
    elif file_kind == "file":
        password_path.write_bytes(content)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "kotaemon.cli",
                "app",
                "init",
                "--force",
                "--json",
                "--auth-mode",
                "password",
            ],
            cwd=str(tmp_path),
            env=_package_mode_env(
                tmp_path,
                overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("password-file validation blocked on a non-regular file")

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert error_fragment in output
    assert str(password_path) not in output


def test_password_file_rejects_oversized_content_without_reading_it_all(
    monkeypatch,
    tmp_path,
):
    password_path = tmp_path / "oversized-secret.txt"
    password_path.write_bytes(b"Aa1!" * 1025)
    monkeypatch.setenv("MARA_ADMIN_PASSWORD_FILE", str(password_path))

    with pytest.raises(click.ClickException, match="at most 4096 bytes") as error:
        app_init_module.read_admin_password_file()

    assert str(password_path) not in str(error.value)
    assert "Aa1!" not in str(error.value)


def test_password_file_accepts_symlink_to_regular_secret(monkeypatch, tmp_path):
    target_path = tmp_path / "mounted-secret-target.txt"
    target_path.write_text("SymlinkHorse7!\n", encoding="utf-8")
    password_path = tmp_path / "mounted-secret-link.txt"
    password_path.symlink_to(target_path)
    monkeypatch.setenv("MARA_ADMIN_PASSWORD_FILE", str(password_path))

    assert app_init_module.read_admin_password_file() == "SymlinkHorse7!"


@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_app_init_password_mode_refuses_noninteractive_input_without_file(
    tmp_path,
    json_output,
):
    args = ["app", "init", "--force", "--auth-mode", "password"]
    if json_output:
        args.append("--json")

    result = _run_package_mode_cli(tmp_path, *args)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "MARA_ADMIN_PASSWORD_FILE" in output
    assert "interactive" in output
    assert not (tmp_path / "config" / "Kotaemon" / "flowsettings.py").exists()


def _read_users(database_path):
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            'SELECT username, username_lower, password, admin FROM "user" '
            "ORDER BY username_lower"
        ).fetchall()


def _users_by_name(database_path):
    return {row[1]: row for row in _read_users(database_path)}


def test_app_init_password_file_creates_bcrypt_admin_without_secret_leakage(tmp_path):
    password = "FileHorse7!"
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text(password + "\n", encoding="utf-8")

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        "--admin-user",
        "Operator",
        env_overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    database_path = Path(payload["data_dir"]) / "user_data" / "sql.db"
    users = _read_users(database_path)
    assert len(users) == 1
    username, username_lower, password_hash, is_admin = users[0]
    assert (username, username_lower, is_admin) == ("Operator", "operator", 1)
    assert password_hash.startswith("$mara-bcrypt-sha256$$2b$12$")
    assert verify_password(password, password_hash) == (True, None)

    env_text = Path(payload["env_path"]).read_text(encoding="utf-8")
    example_text = Path(payload["env_example_path"]).read_text(encoding="utf-8")
    public_text = result.stdout + result.stderr + env_text + example_text
    assert "MARA_AUTH_MODE=password" in env_text
    assert "MARA_ADMIN_PASSWORD_FILE" not in env_text
    assert password not in public_text
    assert password_hash not in public_text
    assert str(password_path) not in public_text


def test_app_init_force_resets_named_user_without_modifying_other_users(tmp_path):
    original_password = "OriginalHorse7!"
    replacement_password = "ReplacementHorse8!"
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text(original_password, encoding="utf-8")
    env_overrides = {"MARA_ADMIN_PASSWORD_FILE": str(password_path)}

    created = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        "--admin-user",
        "Operator",
        env_overrides=env_overrides,
    )
    assert created.returncode == 0, created.stdout + "\nSTDERR:\n" + created.stderr
    payload = _extract_json_payload(created.stdout)
    database_path = Path(payload["data_dir"]) / "user_data" / "sql.db"
    other_hash = "$mara-bcrypt-sha256$$2b$12$RwhUy721./dNELW47maHVeTbdjFVSiiZZLHJ1XGD5gqvLWMjafAt."
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'UPDATE "user" SET admin = 0 WHERE username_lower = "operator"'
        )
        connection.execute(
            'INSERT INTO "user" (id, username, username_lower, password, admin) '
            "VALUES (?, ?, ?, ?, ?)",
            ("other-user", "OtherUser", "otheruser", other_hash, 0),
        )
    original_hash = _users_by_name(database_path)["operator"][2]
    Path(payload["flowsettings_path"]).unlink()
    password_path.write_text(replacement_password + "\n", encoding="utf-8")

    refused = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--json",
        "--auth-mode",
        "password",
        "--admin-user",
        "operator",
        env_overrides=env_overrides,
    )

    assert refused.returncode != 0
    assert "--force" in refused.stdout + refused.stderr
    refused_users = _users_by_name(database_path)
    assert refused_users["operator"][2:] == (original_hash, 0)

    reset = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        "--admin-user",
        "operator",
        env_overrides=env_overrides,
    )

    assert reset.returncode == 0, reset.stdout + "\nSTDERR:\n" + reset.stderr
    reset_users = _users_by_name(database_path)
    other = reset_users["otheruser"]
    target = reset_users["operator"]
    assert other == ("OtherUser", "otheruser", other_hash, 0)
    assert target[:2] == ("Operator", "operator")
    assert target[2] != original_hash
    assert verify_password(replacement_password, target[2]) == (True, None)
    assert target[3] == 1
    public_output = created.stdout + created.stderr + refused.stdout + refused.stderr
    public_output += reset.stdout + reset.stderr
    assert original_password not in public_output
    assert replacement_password not in public_output
    assert str(password_path) not in public_output


def test_app_init_forces_package_runtime_and_leaves_workspace_database_unchanged(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_database = tmp_path / "workspace-live.db"
    with sqlite3.connect(workspace_database) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('unchanged')")
    before_hash = hashlib.sha256(workspace_database.read_bytes()).hexdigest()
    (workspace / "flowsettings.py").write_text(
        "from theflow.settings.default import *  # noqa\n"
        f"KH_DATABASE = {f'sqlite:///{workspace_database}'!r}\n"
        "KH_ENABLE_ALEMBIC = False\n",
        encoding="utf-8",
    )
    password_path = tmp_path / "admin-secret.txt"
    password_path.write_text("PackageHorse7!", encoding="utf-8")

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--json",
        "--auth-mode",
        "password",
        env_overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
        cwd=workspace,
    )

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    payload = _extract_json_payload(result.stdout)
    package_database = Path(payload["data_dir"]) / "user_data" / "sql.db"
    assert package_database != workspace_database
    assert _read_users(package_database)[0][:2] == ("admin", "admin")
    assert hashlib.sha256(workspace_database.read_bytes()).hexdigest() == before_hash


def test_app_init_password_file_rejects_weak_password_without_leaking_secret(tmp_path):
    password = "weak-secret"
    password_path = tmp_path / "named-sensitive-location.txt"
    password_path.write_text(password, encoding="utf-8")

    result = _run_package_mode_cli(
        tmp_path,
        "app",
        "init",
        "--force",
        "--auth-mode",
        "password",
        env_overrides={"MARA_ADMIN_PASSWORD_FILE": str(password_path)},
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "uppercase" in output
    assert password not in output
    assert str(password_path) not in output


def test_app_init_help_exposes_auth_options_but_no_plaintext_password_option(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "init", "--help")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    assert "--auth-mode [auto|local|password|sso]" in result.stdout
    assert "--admin-user TEXT" in result.stdout
    assert "--admin-password" not in result.stdout


def test_app_help_lists_action_navigation(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "--help")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    for token in [
        "Action guide:",
        "Initialize user config",
        "MARA-app-init",
        "Inspect runtime health",
        "MARA-app-doctor",
        "Launch the packaged Web UI",
        "MARA-app-run",
    ]:
        assert token in result.stdout


def test_app_doctor_help_lists_platform_skill(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "doctor", "--help")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    assert "Platform skill: MARA-app-doctor" in result.stdout


def test_app_run_help_lists_platform_skill(tmp_path):
    result = _run_package_mode_cli(tmp_path, "app", "run", "--help")

    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr
    assert "Platform skill: MARA-app-run" in result.stdout


def test_app_run_share_forwards_explicit_share_to_policy_launcher(monkeypatch):
    calls = []
    monkeypatch.setattr(cli_module, "_bootstrap_runtime_settings", lambda: None)

    from ktem import launcher as launcher_module

    monkeypatch.setattr(
        launcher_module,
        "launch_app",
        lambda **kwargs: calls.append(kwargs),
    )

    result = CliRunner().invoke(
        cli_module.app,
        ["run", "--share", "--no-browser"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [{"host": None, "port": None, "share": True, "inbrowser": False}]


def test_source_app_uses_shared_policy_aware_launcher():
    repo_root = Path(__file__).resolve().parents[3]
    app_source = (repo_root / "app.py").read_text(encoding="utf-8")
    launcher_source = (repo_root / "libs/ktem/ktem/launcher.py").read_text(
        encoding="utf-8"
    )

    assert "from ktem.launcher import launch_app" in app_source
    assert "resolve_gradio_server_port(port)" in launcher_source
    assert 'os.getenv("PORT", "8000")' not in app_source
