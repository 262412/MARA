from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pytest_runtime_isolation import TestRuntimePaths  # noqa: E402

EXPECTED_WHEELS = {
    "ktem": "ktem/",
    "kotaemon": "kotaemon/",
    "mara-research-cli": "slide_cli/",
    "mara-app": ".dist-info/",
}


def _wheel_for(dist_root: Path, distribution: str) -> Path:
    wheels = sorted((dist_root / distribution).glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected one wheel for {distribution}, found {len(wheels)} in "
            f"{dist_root / distribution}."
        )
    return wheels[0]


def validate_wheel_contents(wheels: dict[str, Path]) -> None:
    for distribution, wheel in wheels.items():
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        if not any(".dist-info/METADATA" in name for name in names):
            raise RuntimeError(f"{wheel.name} has no distribution metadata.")
        expected = EXPECTED_WHEELS[distribution]
        if expected == ".dist-info/":
            continue
        if not any(name.startswith(expected) for name in names):
            raise RuntimeError(f"{wheel.name} does not contain {expected}.")


def _venv_python(venv: Path) -> Path:
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return venv / suffix


def _venv_command(venv: Path, name: str) -> Path:
    suffix = f"Scripts/{name}.exe" if os.name == "nt" else f"bin/{name}"
    return venv / suffix


def _run(command: list[str | Path], *, env: dict[str, str]) -> None:
    printable = [str(item) for item in command]
    print("[wheel-smoke]", " ".join(printable), flush=True)
    subprocess.run(printable, cwd=REPO_ROOT, env=env, check=True)


def run_smoke(dist_root: Path) -> None:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required for the clean-wheel smoke test.")
    wheels = {
        distribution: _wheel_for(dist_root, distribution)
        for distribution in EXPECTED_WHEELS
    }
    validate_wheel_contents(wheels)
    with tempfile.TemporaryDirectory(prefix="mara-wheel-smoke-") as temp_dir:
        venv = Path(temp_dir) / "venv"
        runtime = TestRuntimePaths.from_root(Path(temp_dir) / "runtime")
        runtime.create_directories()
        env = os.environ.copy()
        env.update(runtime.environment())
        _run([uv, "venv", "--python", sys.executable, str(venv)], env=env)
        python = _venv_python(venv)
        constraints = Path(temp_dir) / "locked-constraints.txt"
        _run(
            [
                uv,
                "export",
                "--frozen",
                "--all-packages",
                "--all-extras",
                "--no-dev",
                "--no-emit-workspace",
                "--no-hashes",
                "--no-header",
                "--no-annotate",
                "--output-file",
                constraints,
            ],
            env=env,
        )
        _run(
            [
                uv,
                "pip",
                "install",
                "--python",
                python,
                "--constraint",
                constraints,
                *wheels.values(),
            ],
            env=env,
        )
        _run([uv, "pip", "check", "--python", python], env=env)
        for executable in ("MARA", "MARA-cli"):
            _run([_venv_command(venv, executable), "--help"], env=env)
        mara = _venv_command(venv, "MARA")
        _run([mara, "docqa", "--help"], env=env)
        _run([mara, "app", "--help"], env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install all MARA wheels together in a clean environment."
    )
    parser.add_argument(
        "--dist-root", type=Path, default=REPO_ROOT / "dist" / "publish"
    )
    return parser.parse_args()


def main() -> int:
    try:
        run_smoke(parse_args().dist_root.resolve())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Clean wheel smoke failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
