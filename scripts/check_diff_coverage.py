from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from check_hygiene_baseline import default_base_ref, resolve_merge_base
from run_coverage_gates import PRODUCTION_PATHS

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_PRODUCTION_FILES = {"app.py", "flowsettings.py", "sso_app.py", "sso_app_demo.py"}
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class DiffCoverage:
    covered: int
    total: int
    missing: dict[str, list[int]]

    @property
    def percent(self) -> float:
        return 100.0 if self.total == 0 else self.covered * 100.0 / self.total


def is_production_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in ROOT_PRODUCTION_FILES:
        return True
    if "/tests/" in f"/{normalized}" or "/ktem_tests/" in f"/{normalized}":
        return False
    return any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in PRODUCTION_PATHS.values()
    )


def changed_lines(repo: Path, base_ref: str) -> dict[str, set[int]]:
    merge_base = resolve_merge_base(repo, base_ref)
    result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            "--diff-filter=ACMR",
            merge_base,
            "HEAD",
            "--",
            "*.py",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    changed: dict[str, set[int]] = {}
    current_path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            continue
        match = HUNK_HEADER.match(line)
        if not match or current_path is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        changed.setdefault(current_path, set()).update(range(start, start + count))
    return {path: lines for path, lines in changed.items() if is_production_path(path)}


def _normalized_coverage_files(payload: dict, repo: Path) -> dict[str, dict]:
    normalized: dict[str, dict] = {}
    for raw_path, data in payload.get("files", {}).items():
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(repo)
            except ValueError:
                continue
        normalized[path.as_posix()] = data
    return normalized


def calculate_diff_coverage(
    coverage_json: Path,
    changed: dict[str, set[int]],
    *,
    repo: Path = REPO_ROOT,
) -> DiffCoverage:
    payload = json.loads(coverage_json.read_text(encoding="utf-8"))
    coverage_files = _normalized_coverage_files(payload, repo.resolve())
    covered = 0
    total = 0
    missing: dict[str, list[int]] = {}
    for path, lines in sorted(changed.items()):
        if not is_production_path(path):
            continue
        if path not in coverage_files:
            missing[path] = sorted(lines)
            total += len(lines)
            continue
        data = coverage_files[path]
        executed = set(data.get("executed_lines", []))
        missed = set(data.get("missing_lines", []))
        statements = lines.intersection(executed | missed)
        covered += len(statements.intersection(executed))
        total += len(statements)
        uncovered = sorted(statements.intersection(missed))
        if uncovered:
            missing[path] = uncovered
    return DiffCoverage(covered=covered, total=total, missing=missing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Require coverage for changed production statements."
    )
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--base-ref", default=None)
    parser.add_argument("--minimum", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    try:
        changed = changed_lines(repo, args.base_ref or default_base_ref())
        result = calculate_diff_coverage(args.coverage_json, changed, repo=repo)
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Diff coverage gate could not run: {exc}")
        return 2
    print(
        f"Production diff coverage: {result.percent:.2f}% "
        f"({result.covered}/{result.total} statements)"
    )
    if result.percent >= args.minimum:
        return 0
    for path, lines in result.missing.items():
        print(f"- {path}: uncovered changed lines {', '.join(map(str, lines))}")
    print(f"Required production diff coverage is {args.minimum:.2f}%.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
