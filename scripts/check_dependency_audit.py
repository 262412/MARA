from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "scripts" / "dependency_audit_baseline.json"


@dataclass(frozen=True)
class AuditComparison:
    new_findings: tuple[str, ...]
    resolved_findings: tuple[str, ...]
    new_adverse_statuses: tuple[str, ...]
    resolved_adverse_statuses: tuple[str, ...]


def _finding_key(finding: dict[str, Any]) -> str:
    dependency = finding.get("dependency")
    if not isinstance(dependency, dict):
        raise ValueError("audit finding has no dependency record")
    name = str(dependency.get("name") or "").strip()
    version = str(dependency.get("version") or "").strip()
    finding_id = str(finding.get("id") or "").strip()
    if not name or not version or not finding_id:
        raise ValueError("audit finding is missing name, version, or id")
    return f"{name}=={version}|{finding_id}"


def _status_key(status: dict[str, Any]) -> str:
    name = str(status.get("name") or "").strip()
    state = str(status.get("status") or "").strip()
    if not name or not state:
        raise ValueError("audit adverse status is missing name or status")
    return f"{name}|{state}"


def compare_audit_report(
    report: dict[str, Any],
    baseline: dict[str, Any],
) -> AuditComparison:
    current_findings = {
        _finding_key(item) for item in report.get("vulnerabilities", [])
    }
    known_findings = {str(item) for item in baseline.get("known_findings", [])}
    current_statuses = {
        _status_key(item) for item in report.get("adverse_statuses", [])
    }
    known_statuses = {str(item) for item in baseline.get("known_adverse_statuses", [])}
    return AuditComparison(
        new_findings=tuple(sorted(current_findings - known_findings)),
        resolved_findings=tuple(sorted(known_findings - current_findings)),
        new_adverse_statuses=tuple(sorted(current_statuses - known_statuses)),
        resolved_adverse_statuses=tuple(sorted(known_statuses - current_statuses)),
    )


def _load_profile(
    baseline_path: Path,
    profile: str,
    *,
    project: str,
    python_version: str,
) -> dict[str, Any]:
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or profile not in profiles:
        raise ValueError(f"dependency audit baseline has no profile {profile!r}")
    selected = profiles[profile]
    if not isinstance(selected, dict):
        raise ValueError(f"dependency audit profile {profile!r} is not an object")
    expected = (str(selected.get("project")), str(selected.get("python_version")))
    actual = (project, python_version)
    if expected != actual:
        raise ValueError(
            f"dependency audit profile {profile!r} targets {expected}, got {actual}"
        )
    return selected


def _run_uv_audit(
    *,
    project: str,
    python_version: str,
    python_platform: str,
) -> dict[str, Any]:
    command = [
        "uv",
        "audit",
        "--project",
        project,
        "--frozen",
        "--no-dev",
        "--python-version",
        python_version,
        "--python-platform",
        python_platform,
        "--output-format",
        "json",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"uv audit failed with exit code {completed.returncode}: {completed.stdout}"
        )
    report = json.loads(completed.stdout)
    if not isinstance(report, dict):
        raise ValueError("uv audit JSON output is not an object")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail on dependency findings outside the reviewed baseline."
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument(
        "--python-platform",
        default="x86_64-unknown-linux-gnu",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args(argv)

    try:
        baseline = _load_profile(
            args.baseline,
            args.profile,
            project=args.project,
            python_version=args.python_version,
        )
        report = _run_uv_audit(
            project=args.project,
            python_version=args.python_version,
            python_platform=args.python_platform,
        )
        comparison = compare_audit_report(report, baseline)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"dependency audit failed closed: {error}", file=sys.stderr)
        return 2

    if comparison.resolved_findings or comparison.resolved_adverse_statuses:
        print(
            "dependency audit baseline has "
            f"{len(comparison.resolved_findings)} resolved findings and "
            f"{len(comparison.resolved_adverse_statuses)} resolved statuses"
        )
    if comparison.new_findings or comparison.new_adverse_statuses:
        for finding in comparison.new_findings:
            print(f"new dependency vulnerability: {finding}", file=sys.stderr)
        for status in comparison.new_adverse_statuses:
            print(f"new adverse project status: {status}", file=sys.stderr)
        return 1

    print(
        "dependency audit passed: "
        f"{len(baseline.get('known_findings', []))} frozen legacy findings, "
        f"{len(baseline.get('known_adverse_statuses', []))} frozen legacy statuses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
