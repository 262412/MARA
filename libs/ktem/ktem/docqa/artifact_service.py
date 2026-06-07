from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .artifact_models import normalize_artifact


def list_artifact_records(artifacts: Any) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list):
        return []
    normalized = [normalize_artifact(item) for item in artifacts]
    return deepcopy([item for item in normalized if item is not None])


def get_artifact_record(
    artifacts: Any,
    artifact_id: str,
) -> dict[str, Any] | None:
    lookup = str(artifact_id or "").strip()
    for artifact in list_artifact_records(artifacts):
        if str(artifact.get("artifact_id") or "") == lookup:
            return artifact
    return None


def append_artifact_record(
    artifacts: Any,
    artifact: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = normalize_artifact(artifact)
    if normalized is None:
        raise ValueError("Artifact record is invalid.")
    records = [*list_artifact_records(artifacts), normalized]
    return records, deepcopy(normalized)


def update_artifact_record(
    artifacts: Any,
    artifact_id: str,
    updates: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lookup = str(artifact_id or "").strip()
    updated_artifact: dict[str, Any] | None = None
    updated_records: list[dict[str, Any]] = []
    for artifact in list_artifact_records(artifacts):
        if str(artifact.get("artifact_id") or "") == lookup:
            merged = normalize_artifact({**artifact, **dict(updates or {})})
            if merged is not None:
                artifact = merged
                updated_artifact = merged
        updated_records.append(artifact)
    if updated_artifact is None:
        raise ValueError(f"Artifact '{artifact_id}' does not exist.")
    return updated_records, deepcopy(updated_artifact)


def delete_artifact_record(
    artifacts: list[dict[str, Any]],
    artifact_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lookup = str(artifact_id or "").strip()
    kept: list[dict[str, Any]] = []
    deleted: dict[str, Any] | None = None
    for artifact in artifacts:
        if str(artifact.get("artifact_id") or "") == lookup:
            deleted = artifact
        else:
            kept.append(artifact)
    if deleted is None:
        raise ValueError(f"Artifact '{artifact_id}' does not exist.")
    return kept, deepcopy(deleted)


def record_artifact_export_record(
    artifacts: list[dict[str, Any]],
    artifact_id: str,
    export_record: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lookup = str(artifact_id or "").strip()
    updated_artifact: dict[str, Any] | None = None
    updated_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        if str(artifact.get("artifact_id") or "") != lookup:
            updated_artifacts.append(artifact)
            continue
        updated_artifact = {
            **artifact,
            "exports": [*list(artifact.get("exports", []) or []), export_record],
            "updated_at": export_record["created_at"],
        }
        updated_artifacts.append(updated_artifact)
    if updated_artifact is None:
        raise ValueError(f"Artifact '{artifact_id}' does not exist.")
    return updated_artifacts, deepcopy(updated_artifact)


def build_artifact_note_fields(artifact: dict[str, Any]) -> dict[str, Any]:
    title = str(artifact.get("title") or artifact.get("type") or "Artifact")
    citations = [
        item for item in artifact.get("citations", []) if isinstance(item, dict)
    ]
    lines = [
        f"# {title}",
        "",
        f"Artifact ID: {artifact.get('artifact_id', '')}",
        f"Type: {artifact.get('type', '')}",
        f"Status: {artifact.get('status', '')}",
    ]
    prompt = str(artifact.get("prompt") or "").strip()
    if prompt:
        lines.extend(["", "## Prompt", "", prompt])
    lines.extend(_record_section("Source Scope", artifact.get("source_scope")))
    lines.extend(_record_section("Content", artifact.get("payload")))
    lines.extend(_citation_lines(citations))
    lines.extend(_record_section("Exports", artifact.get("exports")))
    return {
        "title": title,
        "text": "\n".join(lines).rstrip() + "\n",
        "citation_refs": _citation_refs(citations),
    }


def _record_section(title: str, value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    return ["", f"## {title}", "", _stringify_record(value)]


def _stringify_record(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _citation_lines(citations: list[dict[str, Any]]) -> list[str]:
    if not citations:
        return []
    return [
        "",
        "## Citations",
        "",
        *[f"- {_citation_label(item)}" for item in citations],
    ]


def _citation_label(citation: dict[str, Any]) -> str:
    source = str(
        citation.get("source_name")
        or citation.get("source_id")
        or citation.get("citation_id")
        or ""
    ).strip()
    page = str(citation.get("page_label") or "").strip()
    return f"{source} p.{page}" if source and page else source


def _citation_refs(citations: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for citation in citations:
        ref = str(
            citation.get("citation_id") or citation.get("source_id") or ""
        ).strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs
