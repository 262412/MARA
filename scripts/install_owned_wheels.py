"""Install the four pinned MARA wheels into an explicitly owned environment.

This is the local delivery helper, not the repository/canonical environment
installer. The caller supplies an already prepared environment and wheel hashes.
No configuration is inherited or merged after the final spawn validation.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Mapping, TextIO

PACKAGES = {"kotaemon", "ktem", "mara-app", "mara-research-cli"}
_VALUES = {
    "UV_PYTHON_DOWNLOADS": "never",
    "UV_LINK_MODE": "copy",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
}


def _owned_path(value: str | Path, expected: Path) -> Path:
    if not str(value).strip():
        raise ValueError("Empty installer path")
    path = Path(value)
    if not path.is_absolute() or path != expected or path.resolve() != expected:
        raise ValueError("Installer path is outside its declared owned location")
    return path


def _validate_environment(env: dict[str, str], owner: Path) -> None:
    paths = {
        "UV_PROJECT_ENVIRONMENT": owner / "env",
        "UV_CACHE_DIR": owner / "uv-cache",
        "PIP_CACHE_DIR": owner / "pip-cache",
        "XDG_CACHE_HOME": owner / "cache",
        "TEMP": owner / "tmp",
        "TMP": owner / "tmp",
        "TMPDIR": owner / "tmp",
    }
    for name, expected in paths.items():
        _owned_path(env.get(name, ""), expected)
        if not expected.is_dir():
            raise ValueError(f"Owned installer directory is missing: {name}")
    for name, value in _VALUES.items():
        if env.get(name) != value:
            raise ValueError(f"Invalid installer setting: {name}")
    allowed = paths.keys() | _VALUES.keys()
    for name in env:
        upper = name.upper()
        if upper in allowed and name != upper:
            raise ValueError("Ambiguous installer environment casing")
        if upper == "VIRTUAL_ENV" or (
            upper.startswith(("UV_", "PIP_", "PYTHON")) and upper not in allowed
        ):
            raise ValueError(f"Inherited installer override is forbidden: {name}")


def _validate_wheels(wheels: Mapping[Path, str]) -> list[str]:
    paths = []
    packages = []
    for path, digest in wheels.items():
        if (
            not path.is_absolute()
            or path.resolve() != path
            or not path.is_file()
            or path.suffix != ".whl"
        ):
            raise ValueError("Expected an absolute regular wheel path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Pinned wheel hash changed")
        packages.append(path.name.split("-", 1)[0].replace("_", "-"))
        paths.append(str(path))
    if len(packages) != 4 or set(packages) != PACKAGES:
        raise ValueError("Expected exactly the four MARA distributions")
    return paths


def _validate_launch(
    command: list[str], env: dict[str, str], owner: Path, wheels: Mapping[Path, str]
) -> None:
    if not owner.is_absolute() or owner.resolve() != owner or not owner.is_dir():
        raise ValueError("Expected an existing physical owned root")
    _validate_environment(env, owner)
    python = owner / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _owned_path(python, python)
    if not python.is_file() or not (owner / "env/pyvenv.cfg").is_file():
        raise ValueError("Owned Python environment is missing")
    uv = Path(command[0])
    if not uv.is_absolute() or not uv.is_file() or uv.resolve() != uv:
        raise ValueError("Expected the explicitly selected uv executable")
    expected = [
        str(uv),
        "--no-config",
        "--offline",
        "--cache-dir",
        env["UV_CACHE_DIR"],
        "pip",
        "install",
        "--python",
        str(python),
        "--no-index",
        "--no-deps",
        "--reinstall",
        *_validate_wheels(wheels),
    ]
    if command != expected:
        raise ValueError("Final installer arguments differ from the owned contract")


def install_wheels(
    uv: Path,
    *,
    owner: Path,
    wheels: Mapping[Path, str],
    env: Mapping[str, str],
    log: TextIO,
) -> subprocess.CompletedProcess:
    """Validate the exact local argv/env snapshot used by the single spawn.

    The owner is a caller-authorized task root, never discovered from HOME or
    the current directory. Cache/temp directories must exist below that root.
    Rejected input launches no child and creates no cache or environment.
    """
    child_env = dict(env)
    wheel_snapshot = dict(wheels)
    python = owner / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    command = [
        str(uv),
        "--no-config",
        "--offline",
        "--cache-dir",
        child_env.get("UV_CACHE_DIR", ""),
        "pip",
        "install",
        "--python",
        str(python),
        "--no-index",
        "--no-deps",
        "--reinstall",
        *map(str, wheel_snapshot),
    ]
    _validate_launch(command, child_env, owner, wheel_snapshot)
    log.write(
        json.dumps(
            {
                "argv": command,
                "cwd": str(owner),
                "paths": {
                    name: child_env[name]
                    for name in (
                        "UV_PROJECT_ENVIRONMENT",
                        "UV_CACHE_DIR",
                        "PIP_CACHE_DIR",
                        "XDG_CACHE_HOME",
                        "TEMP",
                        "TMP",
                        "TMPDIR",
                    )
                },
                "uv_sha256": hashlib.sha256(uv.read_bytes()).hexdigest(),
                "python_sha256": hashlib.sha256(python.read_bytes()).hexdigest(),
            }
        )
        + "\n"
    )
    log.flush()
    return subprocess.run(
        command,
        cwd=owner,
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=True,
    )
