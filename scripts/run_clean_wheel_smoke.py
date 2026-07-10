from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
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

PACKAGE_ORDER = ("kotaemon", "ktem", "mara-research-cli", "mara-app")
LAYER_IMPORTS = {
    "kotaemon": ("kotaemon",),
    "ktem": ("ktem.index.file.pipelines",),
    "mara-research-cli": ("slide_cli.cli",),
}
KTEM_ASSETS = {
    "ktem/assets/icons/delete.svg",
    "ktem/assets/icons/sidebar.svg",
    "ktem/assets/md/about.md",
    "ktem/assets/md/usage.md",
    "ktem/assets/vendor/pdfjs/LICENSE.pdfjs",
    "ktem/assets/vendor/pdfjs/manifest.json",
    "ktem/assets/vendor/pdfjs/pdfjs-6.1.200-dist.zip",
}


def _wheel_for(dist_root: Path, distribution: str) -> Path:
    wheels = sorted((dist_root / distribution).glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected one wheel for {distribution}, found {len(wheels)} in "
            f"{dist_root / distribution}."
        )
    return wheels[0]


def _sdist_for(dist_root: Path, distribution: str) -> Path:
    sdists = sorted((dist_root / distribution).glob("*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError(
            f"Expected one sdist for {distribution}, found {len(sdists)} in "
            f"{dist_root / distribution}."
        )
    return sdists[0]


def _validate_pdfjs_bytes(read_bytes) -> None:
    manifest_path = "ktem/assets/vendor/pdfjs/manifest.json"
    archive_path = "ktem/assets/vendor/pdfjs/pdfjs-6.1.200-dist.zip"
    manifest = json.loads(read_bytes(manifest_path).decode("utf-8"))
    digest = hashlib.sha256(read_bytes(archive_path)).hexdigest()
    if digest != manifest.get("sha256"):
        raise RuntimeError("ktem PDF.js archive does not match its manifest SHA-256.")


def validate_wheel_contents(wheels: dict[str, Path]) -> None:
    for distribution, wheel in wheels.items():
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            metadata_names = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise RuntimeError(f"{wheel.name} has no unique distribution metadata.")
            metadata = archive.read(metadata_names[0]).decode("utf-8")
            if "License-Expression: Apache-2.0" not in metadata:
                raise RuntimeError(f"{wheel.name} has no Apache-2.0 metadata.")
            for legal_name in ("LICENSE.txt", "NOTICE"):
                if not any(
                    name.endswith(f".dist-info/licenses/{legal_name}") for name in names
                ):
                    raise RuntimeError(f"{wheel.name} does not contain {legal_name}.")
            expected = EXPECTED_WHEELS[distribution]
            if expected != ".dist-info/" and not any(
                name.startswith(expected) for name in names
            ):
                raise RuntimeError(f"{wheel.name} does not contain {expected}.")
            if distribution == "ktem":
                missing = sorted(KTEM_ASSETS - names)
                if missing:
                    raise RuntimeError(
                        f"{wheel.name} is missing ktem assets: {', '.join(missing)}"
                    )
                _validate_pdfjs_bytes(archive.read)


def validate_sdist_contents(sdists: dict[str, Path]) -> None:
    for distribution, sdist_path in sdists.items():
        with tarfile.open(sdist_path, mode="r:gz") as archive:
            member_list = archive.getmembers()
            members = {member.name: member for member in member_list}
            names = set(members)
            for legal_name in ("LICENSE.txt", "NOTICE"):
                if not any(name.endswith(f"/{legal_name}") for name in names):
                    raise RuntimeError(
                        f"{sdist_path.name} does not contain {legal_name}."
                    )
            root_metadata = [
                member
                for member in member_list
                if len(Path(member.name).parts) == 2
                and Path(member.name).name == "PKG-INFO"
            ]
            if len(root_metadata) != 1:
                raise RuntimeError(
                    f"{sdist_path.name} must contain exactly one root PKG-INFO."
                )
            metadata_file = archive.extractfile(root_metadata[0])
            if metadata_file is None:
                raise RuntimeError(f"Cannot read {sdist_path.name} metadata.")
            metadata = metadata_file.read().decode("utf-8")
            if "License-Expression: Apache-2.0" not in metadata:
                raise RuntimeError(f"{sdist_path.name} has no Apache-2.0 metadata.")
            if distribution == "ktem":
                asset_members = {
                    asset: next(
                        (
                            member
                            for name, member in members.items()
                            if name.endswith(f"/{asset}")
                        ),
                        None,
                    )
                    for asset in KTEM_ASSETS
                }
                missing = sorted(
                    asset for asset, member in asset_members.items() if member is None
                )
                if missing:
                    raise RuntimeError(
                        f"{sdist_path.name} is missing ktem assets: {', '.join(missing)}"
                    )

                def read_asset(asset: str) -> bytes:
                    member = asset_members[asset]
                    if member is None:
                        raise RuntimeError(
                            f"Cannot read {asset} from {sdist_path.name}."
                        )
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise RuntimeError(
                            f"Cannot read {asset} from {sdist_path.name}."
                        )
                    return extracted.read()

                _validate_pdfjs_bytes(read_asset)


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


def _write_offline_guard(root: Path) -> Path:
    guard_dir = root / "offline-guard"
    guard_dir.mkdir()
    (guard_dir / "sitecustomize.py").write_text(
        """import socket

class OfflineSocket(socket.socket):
    def connect(self, *args, **kwargs):
        raise RuntimeError(\"network access is forbidden during wheel smoke\")

    def connect_ex(self, *args, **kwargs):
        raise RuntimeError(\"network access is forbidden during wheel smoke\")

def _offline(*args, **kwargs):
    raise RuntimeError(\"network access is forbidden during wheel smoke\")

socket.socket = OfflineSocket
socket.create_connection = _offline
""",
        encoding="utf-8",
    )
    return guard_dir


def _export_constraints(uv: str, root: Path, env: dict[str, str]) -> Path:
    constraints = root / "locked-constraints.txt"
    _run(
        [
            uv,
            "export",
            "--locked",
            "--all-packages",
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
    return constraints


def _run_layer_imports(
    distribution: str,
    venv: Path,
    env: dict[str, str],
) -> None:
    modules = LAYER_IMPORTS.get(distribution, ())
    if not modules:
        return
    imports = "; ".join(f"importlib.import_module({module!r})" for module in modules)
    _run(
        [_venv_python(venv), "-c", f"import importlib; {imports}"],
        env=env,
    )


def _install_wheel_layers(
    uv: str,
    venv: Path,
    constraints: Path,
    wheels: dict[str, Path],
    env: dict[str, str],
) -> None:
    python = _venv_python(venv)
    for distribution in PACKAGE_ORDER:
        _run(
            [
                uv,
                "pip",
                "install",
                "--python",
                python,
                "--constraint",
                constraints,
                wheels[distribution],
            ],
            env=env,
        )
        _run([uv, "pip", "check", "--python", python], env=env)
        _run_layer_imports(distribution, venv, env)
    _run(
        [
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--constraint",
            constraints,
            *(wheels[distribution] for distribution in PACKAGE_ORDER),
        ],
        env=env,
    )
    _run([uv, "pip", "check", "--python", python], env=env)  # pip check


def _offline_environment(root: Path, env: dict[str, str]) -> dict[str, str]:
    guard_dir = _write_offline_guard(root)
    offline_env = env.copy()
    offline_env.update(
        {
            "ALL_PROXY": "http://127.0.0.1:9",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "",
            "PIP_NO_INDEX": "1",
            "UV_OFFLINE": "1",
            "PYTHONPATH": os.pathsep.join(
                filter(None, (str(guard_dir), env.get("PYTHONPATH", "")))
            ),
        }
    )
    return offline_env


def _run_offline_runtime_smoke(
    venv: Path,
    runtime: TestRuntimePaths,
    offline_env: dict[str, str],
) -> None:
    for executable in ("MARA", "MARA-cli"):
        _run([_venv_command(venv, executable), "--help"], env=offline_env)
    mara = _venv_command(venv, "MARA")
    _run([mara, "docqa", "--help"], env=offline_env)
    _run([mara, "app", "--help"], env=offline_env)
    _run(
        [mara, "app", "init", "--auth-mode", "local", "--force", "--json"],
        env=offline_env,
    )
    viewer = (
        runtime.app_data_dir / "assets" / "pdfjs" / "6.1.200" / "web" / "viewer.html"
    )
    if not viewer.is_file():
        raise RuntimeError(f"Offline app init did not materialize {viewer}.")


def run_smoke(dist_root: Path) -> None:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required for the clean-wheel smoke test.")
    wheels = {
        distribution: _wheel_for(dist_root, distribution)
        for distribution in EXPECTED_WHEELS
    }
    sdists = {
        distribution: _sdist_for(dist_root, distribution)
        for distribution in EXPECTED_WHEELS
    }
    validate_wheel_contents(wheels)
    validate_sdist_contents(sdists)
    with tempfile.TemporaryDirectory(prefix="mara-wheel-smoke-") as temp_dir:
        smoke_root = Path(temp_dir)
        venv = smoke_root / "venv"
        runtime = TestRuntimePaths.from_root(smoke_root / "runtime")
        runtime.create_directories()
        env = os.environ.copy()
        env.update(runtime.environment())
        _run([uv, "venv", "--python", sys.executable, str(venv)], env=env)
        constraints = _export_constraints(uv, smoke_root, env)
        _install_wheel_layers(uv, venv, constraints, wheels, env)
        _run_offline_runtime_smoke(
            venv,
            runtime,
            _offline_environment(smoke_root, env),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate wheel/sdist contents, install every MARA wheel layer, "
            "run pip check, and smoke the combined offline runtime."
        )
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
