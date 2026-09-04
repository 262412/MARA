#!/opt/mara/.venv/bin/python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class ContainerConfigurationError(RuntimeError):
    pass


def validate_auth(auth_mode: str, password_file: Path) -> None:
    if auth_mode not in {"password", "sso"}:
        raise ValueError(
            "Network-bound MARA containers require MARA_AUTH_MODE=password or sso."
        )
    if auth_mode != "password":
        return
    if not password_file.exists():
        raise ContainerConfigurationError(
            f"Password mode requires a mounted password file at {password_file}."
        )
    if not password_file.is_file():
        raise ContainerConfigurationError(
            f"Mounted password secret must be a regular file: {password_file}."
        )


def ollama_command(target: str) -> list[str] | None:
    if target not in {"lite", "full", "ollama"}:
        raise ContainerConfigurationError(f"Unknown MARA_CONTAINER_TARGET={target!r}.")
    return ["/usr/bin/ollama", "serve"] if target == "ollama" else None


def _runtime_initialized() -> bool:
    command = [
        "/opt/mara/.venv/bin/python",
        "-c",
        "from ktem.runtime_bootstrap import get_runtime_paths; "
        "raise SystemExit(0 if get_runtime_paths().flowsettings_path.is_file() else 1)",
    ]
    return subprocess.run(command, check=False).returncode == 0


def _initialize_runtime(auth_mode: str) -> None:
    if _runtime_initialized():
        if auth_mode == "password":
            from kotaemon.app_init import (
                provision_password_admin,
                read_admin_password_file,
            )

            password = read_admin_password_file()
            if password is None:
                raise ContainerConfigurationError(
                    "Password mode requires MARA_ADMIN_PASSWORD_FILE."
                )
            provision_password_admin(
                username=os.environ.get("MARA_ADMIN_USER", "admin").strip(),
                password=password,
                force=True,
            )
        return
    command = ["/opt/mara/.venv/bin/MARA", "app", "init", "--auth-mode", auth_mode]
    admin_user = os.environ.get("MARA_ADMIN_USER", "admin").strip()
    if auth_mode == "password":
        command.extend(["--admin-user", admin_user])
    command.append("--json")
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    auth_mode = os.environ.get("MARA_AUTH_MODE", "").strip().lower()
    password_file = Path(
        os.environ.get(
            "MARA_ADMIN_PASSWORD_FILE",
            "/run/secrets/mara_admin_password",
        )
    )
    validate_auth(auth_mode, password_file)
    _initialize_runtime(auth_mode)

    target = os.environ.get("MARA_CONTAINER_TARGET", "").strip().lower()
    ollama = ollama_command(target)
    if ollama is not None:
        subprocess.Popen(ollama)

    command = list(argv if argv is not None else sys.argv[1:])
    if not command:
        command = [
            "/opt/mara/.venv/bin/MARA",
            "app",
            "run",
            "--host",
            os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
            "--port",
            os.environ.get("GRADIO_SERVER_PORT", "7860"),
            "--no-browser",
        ]
    os.execvpe(command[0], command, os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
