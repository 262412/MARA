"""Packaged app-init file, password-input, and admin-provisioning services."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import click

MAX_ADMIN_PASSWORD_FILE_BYTES = 4096


@dataclass(frozen=True)
class _FileSnapshot:
    contents: bytes | None
    mode: int | None


def _snapshot_file(path: Path) -> _FileSnapshot:
    try:
        file_stat = path.stat()
        return _FileSnapshot(
            contents=path.read_bytes(),
            mode=stat.S_IMODE(file_stat.st_mode),
        )
    except FileNotFoundError:
        return _FileSnapshot(contents=None, mode=None)


def _atomic_replace_file(path: Path, contents: bytes, *, mode: int | None) -> None:
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as file_obj:
            file_descriptor = -1
            file_obj.write(contents)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        if mode is not None:
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        temp_path.unlink(missing_ok=True)


def _restore_config_files(snapshots: dict[Path, _FileSnapshot]) -> None:
    for path, snapshot in snapshots.items():
        if snapshot.contents is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_replace_file(path, snapshot.contents, mode=snapshot.mode)


def _write_app_init_files_with_snapshots(
    *,
    force: bool,
    auth_mode: str,
) -> tuple[dict, dict[Path, _FileSnapshot]]:
    from ktem.runtime_bootstrap import (
        build_user_env,
        build_user_env_example,
        build_user_flowsettings_template,
        get_runtime_paths,
    )

    runtime_paths = get_runtime_paths()
    runtime_paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime_paths.data_dir.mkdir(parents=True, exist_ok=True)
    runtime_paths.cache_dir.mkdir(parents=True, exist_ok=True)
    if runtime_paths.flowsettings_path.exists() and not force:
        raise click.ClickException(
            f"Config file already exists: {runtime_paths.flowsettings_path}"
        )

    env_example_path = runtime_paths.config_dir / ".env.example"
    file_contents = {
        runtime_paths.flowsettings_path: build_user_flowsettings_template().encode(),
        runtime_paths.env_path: build_user_env(auth_mode=auth_mode).encode(),
        env_example_path: build_user_env_example().encode(),
    }
    snapshots = {path: _snapshot_file(path) for path in file_contents}
    try:
        for path, contents in file_contents.items():
            _atomic_replace_file(path, contents, mode=snapshots[path].mode)
    except Exception:
        _restore_config_files(snapshots)
        raise

    payload = {
        "config_dir": str(runtime_paths.config_dir),
        "data_dir": str(runtime_paths.data_dir),
        "cache_dir": str(runtime_paths.cache_dir),
        "flowsettings_path": str(runtime_paths.flowsettings_path),
        "env_path": str(runtime_paths.env_path),
        "env_example_path": str(env_example_path),
    }
    return payload, snapshots


def write_app_init_files(*, force: bool = False, auth_mode: str = "auto") -> dict:
    payload, _snapshots = _write_app_init_files_with_snapshots(
        force=force,
        auth_mode=auth_mode,
    )
    return payload


def read_admin_password_file() -> str | None:
    password_file = os.environ.get("MARA_ADMIN_PASSWORD_FILE")
    if not password_file or not password_file.strip():
        return None

    file_descriptor = None
    open_flags = (
        os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        file_descriptor = os.open(password_file, open_flags)
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise click.ClickException(
                "MARA_ADMIN_PASSWORD_FILE must name an existing regular file."
            )
        password_bytes = os.read(file_descriptor, MAX_ADMIN_PASSWORD_FILE_BYTES + 1)
    except OSError:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must name an existing regular file."
        ) from None
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)

    if len(password_bytes) > MAX_ADMIN_PASSWORD_FILE_BYTES:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must contain at most 4096 bytes."
        )
    try:
        password = password_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must contain valid UTF-8."
        ) from None

    if password.endswith("\r\n"):
        password = password[:-2]
    elif password.endswith("\n"):
        password = password[:-1]
    if "\r" in password or "\n" in password:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must contain exactly one password line."
        )
    if not password:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must contain one nonempty line."
        )
    return password


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def acquire_admin_password(*, json_output: bool) -> str:
    password = read_admin_password_file()
    if password is not None:
        return password
    if json_output or not is_interactive_terminal():
        raise click.ClickException(
            "Password mode requires MARA_ADMIN_PASSWORD_FILE when --json is "
            "used or the terminal is non-interactive."
        )
    return click.prompt(
        "Admin password",
        hide_input=True,
        confirmation_prompt=True,
        type=str,
    )


def provision_password_admin(*, username: str, password: str, force: bool) -> None:
    from ktem.runtime_bootstrap import bootstrap_packaged_runtime_settings

    bootstrap_packaged_runtime_settings()

    from ktem.auth.policy import AuthConfigurationError
    from ktem.auth.service import provision_password_admin as provision_admin

    try:
        provision_admin(username=username, password=password, force=force)
    except AuthConfigurationError as exc:
        raise click.ClickException(str(exc)) from None


def preflight_password_admin(*, username: str, password: str, force: bool) -> None:
    from ktem.runtime_bootstrap import bootstrap_packaged_runtime_settings

    bootstrap_packaged_runtime_settings()

    from ktem.auth.policy import AuthConfigurationError
    from ktem.auth.service import preflight_password_admin as preflight_admin

    try:
        preflight_admin(username=username, password=password, force=force)
    except AuthConfigurationError as exc:
        raise click.ClickException(str(exc)) from None


def initialize_password_app(
    *,
    username: str,
    password: str,
    force: bool,
) -> dict:
    preflight_password_admin(username=username, password=password, force=force)
    payload, snapshots = _write_app_init_files_with_snapshots(
        force=force,
        auth_mode="password",
    )
    try:
        provision_password_admin(username=username, password=password, force=force)
    except Exception:
        _restore_config_files(snapshots)
        raise
    return payload
