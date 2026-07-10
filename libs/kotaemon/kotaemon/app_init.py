"""Packaged app-init file, password-input, and admin-provisioning services."""

from __future__ import annotations

import os
import stat
import sys

import click


def write_app_init_files(*, force: bool = False, auth_mode: str = "auto") -> dict:
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

    runtime_paths.flowsettings_path.write_text(
        build_user_flowsettings_template(),
        encoding="utf-8",
    )
    runtime_paths.env_path.write_text(
        build_user_env(auth_mode=auth_mode),
        encoding="utf-8",
    )
    env_example_path = runtime_paths.config_dir / ".env.example"
    env_example_path.write_text(build_user_env_example(), encoding="utf-8")

    return {
        "config_dir": str(runtime_paths.config_dir),
        "data_dir": str(runtime_paths.data_dir),
        "cache_dir": str(runtime_paths.cache_dir),
        "flowsettings_path": str(runtime_paths.flowsettings_path),
        "env_path": str(runtime_paths.env_path),
        "env_example_path": str(env_example_path),
    }


def read_admin_password_file() -> str | None:
    password_file = os.environ.get("MARA_ADMIN_PASSWORD_FILE")
    if not password_file or not password_file.strip():
        return None

    try:
        with open(password_file, "rb") as file_obj:
            if not stat.S_ISREG(os.fstat(file_obj.fileno()).st_mode):
                raise click.ClickException(
                    "MARA_ADMIN_PASSWORD_FILE must name an existing regular file."
                )
            password_line = file_obj.readline()
            extra_content = file_obj.read(1)
    except click.ClickException:
        raise
    except OSError:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must name an existing regular file."
        ) from None

    if extra_content:
        raise click.ClickException(
            "MARA_ADMIN_PASSWORD_FILE must contain exactly one password line."
        )
    try:
        password = password_line.decode("utf-8")
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
