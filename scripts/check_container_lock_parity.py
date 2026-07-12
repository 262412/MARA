from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import tomli

REPO_ROOT = Path(__file__).resolve().parents[1]
FIRST_PARTY = {
    "kotaemon",
    "ktem",
    "mara-app",
    "mara-container-runtime",
    "mara-research-cli",
}
CONTAINER_VARIANTS = {"torch"}
FORBIDDEN_CONTAINER_PACKAGES = {"llama-cpp-python", "triton"}


def _versions(lock_path: Path) -> dict[str, set[str]]:
    lock = tomli.loads(lock_path.read_text(encoding="utf-8"))
    versions: dict[str, set[str]] = defaultdict(set)
    for package in lock["package"]:
        if "version" in package:
            versions[package["name"]].add(package["version"])
    return dict(versions)


def check_lock_parity(root_lock: Path, container_lock: Path) -> list[str]:
    root = _versions(root_lock)
    container = _versions(container_lock)
    errors = []
    for name, versions in sorted(container.items()):
        if name in FIRST_PARTY or name in CONTAINER_VARIANTS:
            continue
        missing = versions - root.get(name, set())
        if missing:
            errors.append(
                f"{name} container versions {sorted(missing)} are absent from root lock"
            )
    forbidden = FORBIDDEN_CONTAINER_PACKAGES & container.keys()
    forbidden.update(name for name in container if name.startswith("nvidia-"))
    if forbidden:
        errors.append(
            "container lock includes GPU/source-build packages: "
            + ", ".join(sorted(forbidden))
        )
    if container.get("torch") != {"2.8.0", "2.8.0+cpu"}:
        errors.append(f"unexpected container torch versions: {container.get('torch')}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare root and container locks.")
    parser.add_argument("--root-lock", type=Path, default=REPO_ROOT / "uv.lock")
    parser.add_argument(
        "--container-lock", type=Path, default=REPO_ROOT / "docker/uv.lock"
    )
    args = parser.parse_args(argv)
    errors = check_lock_parity(args.root_lock, args.container_lock)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Container lock matches root runtime versions; CPU torch is isolated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
