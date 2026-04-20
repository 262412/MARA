from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST_ROOT = REPO_ROOT / "dist" / "publish"


@dataclass(frozen=True)
class PackageSpec:
    name: str
    path: Path


PACKAGE_ORDER = (
    PackageSpec("ktem", REPO_ROOT / "libs" / "ktem"),
    PackageSpec("kotaemon", REPO_ROOT / "libs" / "kotaemon"),
    PackageSpec("kotaemon-app", REPO_ROOT),
)

PACKAGE_BY_NAME = {package.name: package for package in PACKAGE_ORDER}

REPOSITORIES = {
    "testpypi": {
        "url": "https://test.pypi.org/legacy/",
        "token_env": "TEST_PYPI_API_TOKEN",
    },
    "pypi": {
        "url": "https://upload.pypi.org/legacy/",
        "token_env": "PYPI_API_TOKEN",
    },
}


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    printable = " ".join(command)
    print(f"[run] ({cwd}) {printable}")
    completed = subprocess.run(command, cwd=str(cwd), env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _python_module_available(module_name: str) -> bool:
    command = [sys.executable, "-c", f"import {module_name}"]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _ensure_tooling() -> None:
    missing = [
        module_name
        for module_name in ("build", "twine")
        if not _python_module_available(module_name)
    ]
    if not missing:
        return

    joined = ", ".join(missing)
    raise SystemExit(
        "Missing required build tooling: "
        f"{joined}. Install it with `{sys.executable} -m pip install build twine`."
    )


def _resolve_packages(requested: list[str] | None) -> list[PackageSpec]:
    if not requested:
        return list(PACKAGE_ORDER)

    unknown = [name for name in requested if name not in PACKAGE_BY_NAME]
    if unknown:
        choices = ", ".join(PACKAGE_BY_NAME)
        raise SystemExit(
            f"Unknown package selection: {', '.join(unknown)}. Valid packages: {choices}"
        )
    return [PACKAGE_BY_NAME[name] for name in requested]


def _dist_dir(dist_root: Path, package: PackageSpec) -> Path:
    return dist_root / package.name


def _build_package(package: PackageSpec, dist_root: Path) -> None:
    output_dir = _dist_dir(dist_root, package)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(output_dir),
        ],
        cwd=package.path,
    )


def _artifact_paths(package: PackageSpec, dist_root: Path) -> list[Path]:
    output_dir = _dist_dir(dist_root, package)
    artifacts = sorted(path for path in output_dir.iterdir() if path.is_file())
    if not artifacts:
        raise SystemExit(f"No artifacts were built for {package.name} in {output_dir}")
    return artifacts


def _twine_check(package: PackageSpec, dist_root: Path) -> None:
    artifacts = _artifact_paths(package, dist_root)
    _run(
        [sys.executable, "-m", "twine", "check", *[str(path) for path in artifacts]],
        cwd=REPO_ROOT,
    )


def _twine_upload(
    package: PackageSpec,
    dist_root: Path,
    repository: str,
    *,
    skip_existing: bool,
) -> None:
    repo = REPOSITORIES[repository]
    token_env = repo["token_env"]
    token = os.environ.get(token_env, "").strip()
    if not token:
        raise SystemExit(
            f"Missing required token environment variable: {token_env}"
        )

    artifacts = _artifact_paths(package, dist_root)
    command = [
        sys.executable,
        "-m",
        "twine",
        "upload",
        "--non-interactive",
        "--repository-url",
        repo["url"],
    ]
    if skip_existing:
        command.append("--skip-existing")
    command.extend(str(path) for path in artifacts)

    upload_env = os.environ.copy()
    upload_env.setdefault("TWINE_USERNAME", "__token__")
    upload_env["TWINE_PASSWORD"] = token
    _run(command, cwd=REPO_ROOT, env=upload_env)


def cmd_build(args: argparse.Namespace) -> int:
    _ensure_tooling()
    dist_root = Path(args.outdir).resolve()
    for package in _resolve_packages(args.packages):
        _build_package(package, dist_root)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    _ensure_tooling()
    dist_root = Path(args.outdir).resolve()
    packages = _resolve_packages(args.packages)
    if args.rebuild:
        for package in packages:
            _build_package(package, dist_root)
    for package in packages:
        _twine_check(package, dist_root)
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    _ensure_tooling()
    dist_root = Path(args.outdir).resolve()
    packages = _resolve_packages(args.packages)
    if args.rebuild:
        for package in packages:
            _build_package(package, dist_root)
    if args.check:
        for package in packages:
            _twine_check(package, dist_root)
    for package in packages:
        _twine_upload(
            package,
            dist_root,
            args.repository,
            skip_existing=args.skip_existing,
        )
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    _ensure_tooling()
    dist_root = Path(args.outdir).resolve()
    packages = _resolve_packages(args.packages)
    for package in packages:
        _build_package(package, dist_root)
    for package in packages:
        _twine_check(package, dist_root)
    if args.skip_upload:
        print("[info] Skipping upload step.")
        return 0
    for package in packages:
        _twine_upload(
            package,
            dist_root,
            args.repository,
            skip_existing=args.skip_existing,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and publish Kotaemon Python packages in dependency order."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--outdir",
            default=str(DEFAULT_DIST_ROOT),
            help="Directory to store built distributions.",
        )
        command_parser.add_argument(
            "--packages",
            nargs="*",
            choices=list(PACKAGE_BY_NAME),
            help="Optional subset of packages to process. Defaults to all packages in dependency order.",
        )

    build_parser_ = subparsers.add_parser("build", help="Build wheels and sdists.")
    add_common_arguments(build_parser_)
    build_parser_.set_defaults(func=cmd_build)

    check_parser = subparsers.add_parser(
        "check", help="Run twine check against built artifacts."
    )
    add_common_arguments(check_parser)
    check_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Build fresh artifacts before running twine check.",
    )
    check_parser.set_defaults(func=cmd_check)

    upload_parser = subparsers.add_parser(
        "upload", help="Upload already-built artifacts to TestPyPI or PyPI."
    )
    add_common_arguments(upload_parser)
    upload_parser.add_argument(
        "--repository",
        required=True,
        choices=sorted(REPOSITORIES),
        help="Repository target: testpypi or pypi.",
    )
    upload_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Build fresh artifacts before upload.",
    )
    upload_parser.add_argument(
        "--check",
        action="store_true",
        help="Run twine check before upload.",
    )
    upload_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Pass --skip-existing to twine upload.",
    )
    upload_parser.set_defaults(func=cmd_upload)

    release_parser = subparsers.add_parser(
        "release",
        help="Build, validate, and upload packages in dependency order.",
    )
    add_common_arguments(release_parser)
    release_parser.add_argument(
        "--repository",
        required=True,
        choices=sorted(REPOSITORIES),
        help="Repository target: testpypi or pypi.",
    )
    release_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Pass --skip-existing to twine upload.",
    )
    release_parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Build and validate artifacts without uploading them.",
    )
    release_parser.set_defaults(func=cmd_release)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
