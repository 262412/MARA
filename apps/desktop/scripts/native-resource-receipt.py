"""Record only this CI package's files and remaining owned processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import psutil


def owned_role(info: dict, package: Path, repository: Path) -> str | None:
    executable = info.get("exe")
    if executable and Path(executable).resolve().is_relative_to(package):
        return "packaged_application"
    arguments = info.get("cmdline") or []
    if "sidecar.smoke_embedding_server" in arguments:
        command = Path(arguments[0])
        if not command.is_absolute():
            command = Path(info.get("cwd") or "") / command
        # The venv interpreter may resolve to a system Python symlink.
        if Path(os.path.abspath(command)).is_relative_to(repository):
            return "smoke_model_fixture"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve(strict=True)
    repository = Path(__file__).resolve().parents[3]
    files = []
    invalid_links = []
    for filename in sorted(package.rglob("*")):
        if filename.is_symlink():
            target = os.readlink(filename)
            try:
                contained = filename.resolve(strict=True).is_relative_to(package)
            except (OSError, RuntimeError):
                contained = False
            if Path(target).is_absolute() or not contained:
                invalid_links.append(
                    {"path": filename.relative_to(package).as_posix(), "target": target}
                )
                continue
        if not filename.is_file():
            continue
        relative = filename.relative_to(package)
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": filename.stat().st_size,
                "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
                "hidden_path": any(part.startswith(".") for part in relative.parts),
            }
        )
    remaining = []
    denied = 0
    unavailable = object()
    for process in psutil.process_iter():
        if process.pid == os.getpid():
            continue
        try:
            info = process.as_dict(
                attrs=["pid", "ppid", "exe", "cmdline", "cwd"],
                ad_value=unavailable,
            )
            if any(value is unavailable for value in info.values()):
                denied += 1
                continue
            role = owned_role(info, package, repository)
            if role:
                remaining.append(
                    {"pid": info["pid"], "parent_pid": info["ppid"], "role": role}
                )
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            denied += 1
    receipt = {
        "source_sha": os.environ.get("GITHUB_SHA"),
        "files": files,
        "invalid_package_links": invalid_links,
        "remaining_owned_processes": remaining,
        "unclassified_access_denied": denied,
    }
    args.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}))
    if remaining:
        raise SystemExit("Owned native smoke processes remain after cleanup")
    if invalid_links:
        raise SystemExit("Package links are absolute, outside the package, or unresolved")


if __name__ == "__main__":
    main()
