from __future__ import annotations

from typing import Any

from ktem.docqa.artifact_generation import (
    build_artifact_payload,
    build_planned_artifact,
    supports_artifact_type,
)

from kotaemon.base import RetrievedDocument


def build_artifact_for_pipeline(
    pipeline: Any, understanding: dict[str, Any]
) -> dict[str, Any] | None:
    artifact_type = str(getattr(pipeline, "artifact_type", "") or "").strip()
    if not artifact_type:
        task_type = str(understanding.get("task_type") or "")
        artifact_type = task_type if task_type != "qa" else ""
    if not supports_artifact_type(artifact_type):
        return None
    evidence = _artifact_evidence(list(getattr(pipeline, "_mara_last_docs", [])))
    if not evidence:
        return build_planned_artifact(artifact_type)
    return build_artifact_payload(artifact_type, evidence)


def _excerpt(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _artifact_evidence(docs: list[RetrievedDocument]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for doc in docs:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        excerpt = _excerpt(
            str(getattr(doc, "text", "") or getattr(doc, "content", "") or "")
        )
        if not excerpt:
            continue
        evidence.append(
            {
                "evidence_id": str(getattr(doc, "doc_id", "") or "").strip(),
                "file_id": str(metadata.get("file_id") or "").strip(),
                "file_name": str(metadata.get("file_name") or "").strip(),
                "page_label": str(metadata.get("page_label") or "").strip(),
                "excerpt": excerpt,
            }
        )
    return evidence
