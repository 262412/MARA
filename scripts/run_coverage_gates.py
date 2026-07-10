from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_FLOORS = {
    "benchmark": 90,
    "slide_cli": 70,
    "kotaemon": 60,
    "ktem": 50,
}
PRODUCTION_PATHS = {
    "benchmark": "benchmark",
    "slide_cli": "libs/slide_cli/slide_cli",
    "kotaemon": "libs/kotaemon/kotaemon",
    "ktem": "libs/ktem/ktem",
}
COVERAGE_OMIT = (
    "*/tests/*",
    "*/ktem_tests/*",
    "*/conftest.py",
    "*/.venv/*",
    "*/.superpowers/*",
    "*/.playwright-cli/*",
)
TEST_SUITES = (
    ("benchmark/tests", "tests"),
    ("libs/kotaemon",),
    ("libs/ktem/ktem_tests",),
    ("libs/slide_cli",),
)
SOURCE_PATHS = (
    "benchmark",
    "libs/kotaemon/kotaemon",
    "libs/ktem/ktem",
    "libs/slide_cli/slide_cli",
)
ROOT_SOURCE_MODULES = ("app", "flowsettings", "sso_app", "sso_app_demo")


def _run(command: list[str], *, env: dict[str, str]) -> None:
    print("[coverage]", " ".join(command), flush=True)
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)


def write_coverage_config(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "coverage.ini"
    source_lines = "\n".join(f"    {path}" for path in (*SOURCE_PATHS, *ROOT_SOURCE_MODULES))
    omit_lines = "\n".join(f"    {pattern}" for pattern in COVERAGE_OMIT)
    config_path.write_text(
        "[run]\n"
        "patch = subprocess\n"
        "parallel = True\n"
        "relative_files = True\n"
        "source =\n"
        f"{source_lines}\n"
        "omit =\n"
        f"{omit_lines}\n"
        "\n[report]\n"
        "precision = 2\n",
        encoding="utf-8",
    )
    return config_path


def _coverage_command(
    python: str, config_path: Path, command: str, *arguments: str
) -> list[str]:
    return [
        python,
        "-m",
        "coverage",
        command,
        f"--rcfile={config_path}",
        *arguments,
    ]


def run_gates(output_dir: Path) -> None:
    config_path = write_coverage_config(output_dir)
    coverage_file = output_dir / ".coverage"
    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(coverage_file)
    env["COVERAGE_PROCESS_START"] = str(config_path)
    python = sys.executable
    _run(_coverage_command(python, config_path, "erase"), env=env)
    for suite in TEST_SUITES:
        _run(
            _coverage_command(
                python,
                config_path,
                "run",
                "-m",
                "pytest",
                "-q",
                *suite,
            ),
            env=env,
        )
    _run(_coverage_command(python, config_path, "combine"), env=env)
    for name, floor in COVERAGE_FLOORS.items():
        _run(
            _coverage_command(
                python,
                config_path,
                "report",
                f"--fail-under={floor}",
                "--precision=2",
                f"--include={PRODUCTION_PATHS[name]}/*",
            ),
            env=env,
        )
    _run(
        _coverage_command(
            python, config_path, "xml", "-o", str(output_dir / "coverage.xml")
        ),
        env=env,
    )
    _run(
        _coverage_command(
            python,
            config_path,
            "json",
            "-o",
            str(output_dir / "coverage.json"),
        ),
        env=env,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MARA package coverage floors.")
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "coverage-artifacts"
    )
    return parser.parse_args()


def main() -> int:
    run_gates(parse_args().output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
