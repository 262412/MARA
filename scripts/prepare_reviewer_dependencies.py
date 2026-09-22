"""Export main's runtime lock and prebuild dependencies lacking Windows wheels."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tomli
from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def source_requirements(lock: dict, text: str) -> list[str]:
    packages = {
        (canonicalize_name(p["name"]), p["version"]): p
        for p in lock["package"]
        if "version" in p
    }
    tags = set(sys_tags())
    selected = []
    for block in re.split(r"\n(?=[a-zA-Z0-9])", text.strip()):
        requirement = Requirement(block.split("\\\n")[0].strip())
        if requirement.marker and not requirement.marker.evaluate():
            continue
        version = next(iter(requirement.specifier)).version
        package = packages[(canonicalize_name(requirement.name), version)]
        compatible = False
        for wheel in package.get("wheels", []):
            filename = unquote(urlsplit(wheel["url"]).path.rsplit("/", 1)[-1])
            if parse_wheel_filename(filename)[3] & tags:
                compatible = True
                break
        if not compatible:
            selected.append(block)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    if os.name != "nt" or sys.version_info[:2] != (3, 10) or sys.maxsize < 2**32:
        raise SystemExit(
            "Build this Windows package using 64-bit CPython 3.10 on Windows"
        )
    output = args.output_dir.resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit("Use a build directory outside the repository")
    output.mkdir(parents=True, exist_ok=True)
    requirements = output / "runtime-requirements.txt"
    subprocess.run(
        [
            args.uv,
            "export",
            "--frozen",
            "--all-packages",
            "--no-dev",
            "--no-emit-workspace",
            "--no-header",
            "--no-annotate",
            "--output-file",
            str(requirements),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    lock = tomli.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    blocks = source_requirements(lock, requirements.read_text(encoding="utf-8"))
    source_lock = output / "source-requirements.txt"
    source_lock.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    print(f"Prebuilding {len(blocks)} locked dependencies")
    if blocks:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--require-hashes",
                "--wheel-dir",
                str(output / "wheels" / "vendor"),
                "--requirement",
                str(source_lock),
            ],
            cwd=output,
            check=True,
        )


if __name__ == "__main__":
    main()
