from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

_NON_ALPHANUMERIC_RE = re.compile(r"[^a-z0-9]+")
_TIMESTAMP_PREFIX_RE = re.compile(r"^\d{8}[_-]\d{6}[_-]")


class AmbiguousArtifactError(ValueError):
    """Raised when an artifact query has more than one valid result."""


def canonical_suite_key(value: str) -> str:
    """Return the boundary key shared by job tables and artifact directories."""

    normalized = _NON_ALPHANUMERIC_RE.sub("-", str(value or "").strip().lower())
    return normalized.strip("-")


def resolve_artifact_dir(
    root: Path,
    *,
    suite_name: str,
    job_id: str = "",
    required_artifacts: Iterable[str] = (),
) -> Path | None:
    """Resolve one complete artifact directory without silently picking a duplicate."""

    if not root.exists():
        return None
    target_key = canonical_suite_key(suite_name)
    required = tuple(required_artifacts)
    matches = [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and _artifact_is_complete(path, required)
        and _suite_matches(_artifact_suite_key(path), target_key)
    ]
    if not matches:
        return None

    normalized_job_id = str(job_id or "").strip()
    if normalized_job_id:
        job_matches = [
            path for path in matches if _artifact_has_job_id(path, normalized_job_id)
        ]
        if len(job_matches) == 1:
            return job_matches[0]
        if len(job_matches) > 1:
            raise _ambiguous_error(suite_name, normalized_job_id, job_matches)

    if len(matches) == 1:
        return matches[0]
    raise _ambiguous_error(suite_name, normalized_job_id, matches)


def _artifact_is_complete(path: Path, required_artifacts: tuple[str, ...]) -> bool:
    return all((path / filename).is_file() for filename in required_artifacts)


def _artifact_suite_key(path: Path) -> str:
    summary_path = path / "summary.json"
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary = {}
        suite_name = (
            str(summary.get("suite_name") or "") if isinstance(summary, dict) else ""
        )
        if suite_name:
            return canonical_suite_key(suite_name)
    name = _TIMESTAMP_PREFIX_RE.sub("", path.name)
    return canonical_suite_key(name)


def _suite_matches(candidate_key: str, target_key: str) -> bool:
    return candidate_key == target_key or candidate_key.startswith(f"{target_key}-")


def _artifact_has_job_id(path: Path, job_id: str) -> bool:
    job_key = canonical_suite_key(job_id)
    suite_key = _artifact_suite_key(path)
    path_key = canonical_suite_key(path.name)
    return suite_key.endswith(f"-{job_key}") or path_key.endswith(f"-{job_key}")


def _ambiguous_error(
    suite_name: str,
    job_id: str,
    matches: list[Path],
) -> AmbiguousArtifactError:
    job_text = f" and job_id={job_id!r}" if job_id else ""
    candidates = "\n".join(f"- {path}" for path in matches)
    return AmbiguousArtifactError(
        f"Ambiguous artifacts for suite_name={suite_name!r}{job_text}:\n{candidates}"
    )
