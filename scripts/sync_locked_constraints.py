from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS_PATH = REPO_ROOT / "constraints.txt"
EXPORT_COMMAND = (
    "uv",
    "export",
    "--locked",
    "--all-packages",
    "--no-dev",
    "--no-hashes",
    "--no-emit-workspace",
    "--no-header",
    "--no-annotate",
)
HEADER = (
    "# Generated from uv.lock; local source packages are version-pinned.\n"
    "# Regenerate: python scripts/sync_locked_constraints.py\n"
    "# Verify: python scripts/sync_locked_constraints.py --check\n"
)


def render_locked_constraints() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to synchronize constraints.txt")
    command = [uv, *EXPORT_COMMAND[1:]]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"uv export failed ({result.returncode}): {detail}")
    body = result.stdout.strip()
    if not body:
        raise RuntimeError("uv export produced an empty runtime constraint set")
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    nltk = next(package for package in lock["package"] if package["name"] == "nltk")
    if nltk["source"] != {"directory": "vendor/nltk"}:
        raise RuntimeError("NLTK must resolve to the reviewed local backport")
    lines = body.splitlines()
    if lines.count("./vendor/nltk") != 1:
        raise RuntimeError("Locked export is missing the local NLTK source")
    lines[lines.index("./vendor/nltk")] = f"nltk=={nltk['version']}"
    return HEADER + "\n".join(lines) + "\n"


def write_constraints(content: str) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".constraints-",
        suffix=".tmp",
        dir=CONSTRAINTS_PATH.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, CONSTRAINTS_PATH)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def check_constraints(expected: str) -> bool:
    actual = CONSTRAINTS_PATH.read_text(encoding="utf-8")
    if actual == expected:
        return True
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile="constraints.txt",
        tofile="uv export",
        lineterm="",
    )
    print("\n".join(diff))
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize constraints.txt with the frozen uv.lock runtime."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when constraints.txt differs from the locked runtime export.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        expected = render_locked_constraints()
        if parse_args().check:
            return 0 if check_constraints(expected) else 1
        write_constraints(expected)
    except (OSError, RuntimeError) as exc:
        print(f"Constraint synchronization failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
