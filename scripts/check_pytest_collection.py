from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence

COLLECTION_SUMMARY = re.compile(r"(?m)^(\d+) tests? collected(?: in .*)?$")


def parse_collected_count(output: str) -> int:
    matches = COLLECTION_SUMMARY.findall(output)
    if not matches:
        raise ValueError("pytest output has no collection summary")
    return int(matches[-1])


def run_collection(*, minimum: int, pytest_args: Sequence[str]) -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        *pytest_args,
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(f"Unified pytest collection failed with exit code {result.returncode}.")
        return result.returncode

    try:
        collected = parse_collected_count(result.stdout)
    except ValueError as exc:
        print(f"Unified pytest collection could not be verified: {exc}.")
        return 2

    if collected < minimum:
        print(
            f"Collected {collected} tests, below required minimum {minimum}. "
            "Investigate collection loss instead of lowering the floor."
        )
        return 1
    print(f"Unified pytest collection passed: {collected} tests (minimum {minimum}).")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run unified pytest collection and enforce a minimum count."
    )
    parser.add_argument("--minimum", type=int, default=1260)
    parser.add_argument("pytest_args", nargs="*")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.minimum < 1:
        print("Collection minimum must be positive.")
        return 2
    return run_collection(minimum=args.minimum, pytest_args=args.pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
