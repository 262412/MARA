from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("scripts/codebase_hygiene_baseline.json")
ZERO_SHA = "0" * 40


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _ref_exists(repo: Path, ref: str) -> bool:
    result = _run_git(repo, "cat-file", "-e", f"{ref}^{{commit}}", check=False)
    return result.returncode == 0


def ensure_base_ref(repo: Path, ref: str) -> str:
    if _ref_exists(repo, ref):
        return ref

    fetch = _run_git(
        repo,
        "fetch",
        "--no-tags",
        "--depth=200",
        "origin",
        ref,
        check=False,
    )
    if fetch.returncode == 0 and _ref_exists(repo, "FETCH_HEAD"):
        return "FETCH_HEAD"
    raise RuntimeError(
        f"Cannot resolve base ref {ref!r}. Fetch the PR base or full history first. "
        f"git fetch said: {fetch.stderr.strip()}"
    )


def resolve_merge_base(repo: Path, ref: str) -> str:
    resolved = ensure_base_ref(repo, ref)
    result = _run_git(repo, "merge-base", resolved, "HEAD")
    merge_base = result.stdout.strip()
    if not merge_base:
        raise RuntimeError(f"No merge base found between {resolved!r} and HEAD.")
    return merge_base


def load_baseline_at_revision(repo: Path, revision: str) -> dict[str, Any]:
    result = _run_git(
        repo,
        "show",
        f"{revision}:{BASELINE_PATH.as_posix()}",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"The hygiene baseline is missing at base revision {revision}. "
            "Choose a base revision that contains the ratchet file."
        )
    return json.loads(result.stdout)


def _compare_number(
    violations: list[str], label: str, base: object, current: object
) -> None:
    base_value = int(base or 0)
    current_value = int(current or 0)
    if current_value > base_value:
        violations.append(f"{label} increased from {base_value} to {current_value}")


def _compare_named_exemptions(
    violations: list[str],
    path: str,
    kind: str,
    base: dict[str, object],
    current: dict[str, object],
) -> None:
    for name, current_value in sorted(current.items()):
        if name not in base:
            violations.append(f"{path}: new {kind} exemption {name}")
            continue
        _compare_number(
            violations,
            f"{path}: {kind} {name}",
            base[name],
            current_value,
        )


def _compare_file(
    violations: list[str], path: str, base: dict[str, Any], current: dict[str, Any]
) -> None:
    _compare_number(
        violations,
        f"{path}: module_lines",
        base.get("module_lines"),
        current.get("module_lines"),
    )
    _compare_number(
        violations,
        f"{path}: non_actionable_broad_exceptions",
        base.get("non_actionable_broad_exceptions"),
        current.get("non_actionable_broad_exceptions"),
    )
    for kind in ("function", "class"):
        key = f"{kind}s"
        _compare_named_exemptions(
            violations,
            path,
            kind,
            dict(base.get(key, {})),
            dict(current.get(key, {})),
        )


def compare_baselines(base: dict[str, Any], current: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if current.get("version") != base.get("version"):
        violations.append(
            "baseline schema version changed; review the guard before changing schema"
        )

    base_budgets = dict(base.get("budgets", {}))
    current_budgets = dict(current.get("budgets", {}))
    for name, value in sorted(current_budgets.items()):
        if name not in base_budgets:
            violations.append(f"budgets: new allowance {name}")
            continue
        _compare_number(violations, f"budgets: {name}", base_budgets[name], value)

    base_files = dict(base.get("files", {}))
    for path, entry in sorted(dict(current.get("files", {})).items()):
        if path not in base_files:
            violations.append(f"{path}: new baseline file exemption")
            continue
        _compare_file(violations, path, base_files[path], entry)
    return violations


def _event_base_ref() -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return None
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pull_request = event.get("pull_request") or {}
    base = pull_request.get("base") or {}
    return str(base.get("sha") or "").strip() or None


def default_base_ref() -> str:
    candidates = (
        os.environ.get("MARA_BASE_REF"),
        os.environ.get("GITHUB_BASE_SHA"),
        _event_base_ref(),
        os.environ.get("GITHUB_EVENT_BEFORE"),
        os.environ.get("GITHUB_BASE_REF"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value and value != ZERO_SHA:
            return value
    return "HEAD^"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject hygiene baseline changes that widen technical-debt limits."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    current_path = repo / BASELINE_PATH
    if not current_path.is_file():
        raise SystemExit(f"Current hygiene baseline is missing: {current_path}")

    try:
        merge_base = resolve_merge_base(repo, args.base_ref or default_base_ref())
        base = load_baseline_at_revision(repo, merge_base)
        current = json.loads(current_path.read_text(encoding="utf-8"))
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"Hygiene baseline guard could not run: {exc}")
        return 2

    violations = compare_baselines(base, current)
    if not violations:
        print(f"Hygiene baseline did not widen relative to {merge_base}.")
        return 0
    print("Hygiene baseline debt was widened:")
    for violation in violations:
        print(f"- {violation}")
    print("Reduce or remove the exemption; do not refresh the baseline to pass CI.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
