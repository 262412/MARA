from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

ARTIFACT_STATUS_QUEUED = "queued"
ARTIFACT_STATUS_RUNNING = "running"
ARTIFACT_STATUS_READY = "ready"
ARTIFACT_STATUS_FAILED = "failed"
ARTIFACT_STATUSES = (
    ARTIFACT_STATUS_QUEUED,
    ARTIFACT_STATUS_RUNNING,
    ARTIFACT_STATUS_READY,
    ARTIFACT_STATUS_FAILED,
)
SUPPORTED_ARTIFACT_TYPES = (
    "study_guide",
    "quiz",
    "flashcards",
    "mindmap",
    "slide_outline",
    "briefing_doc",
    "faq",
    "timeline",
    "custom_report",
    "data_table",
    "infographic",
    "slide_deck",
    "audio_overview",
    "video_overview",
)
ARTIFACT_LABELS = {
    "study_guide": "Study Guide",
    "quiz": "Quiz",
    "flashcards": "Flashcards",
    "mindmap": "Mind Map",
    "slide_outline": "Slide Outline",
    "briefing_doc": "Briefing Doc",
    "faq": "FAQ",
    "timeline": "Timeline",
    "custom_report": "Custom Report",
    "data_table": "Data Table",
    "infographic": "Infographic",
    "slide_deck": "Slide Deck",
    "audio_overview": "Audio Overview",
    "video_overview": "Video Overview",
}

_DEFAULT_SCOPE = {"mode": "document", "source_ids": []}


def timestamp(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat()


def artifact_label(artifact_type: Any) -> str:
    value = str(artifact_type or "").strip()
    return ARTIFACT_LABELS.get(value, value.replace("_", " ").title() or "Artifact")


def normalize_source_scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return deepcopy(_DEFAULT_SCOPE)
    mode = str(value.get("mode") or "document").strip() or "document"
    source_ids = _unique_text(value.get("source_ids", []))
    scope: dict[str, Any] = {"mode": mode, "source_ids": source_ids}
    page = value.get("page")
    if page not in (None, ""):
        scope["page"] = page
    note_ids = _unique_text(value.get("note_ids", []))
    if note_ids:
        scope["note_ids"] = note_ids
    return scope


def build_artifact_record(
    *,
    artifact_type: str,
    payload: Any,
    artifact_id: str | None = None,
    title: str = "",
    status: str = ARTIFACT_STATUS_READY,
    prompt: str = "",
    source_scope: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
    exports: list[dict[str, Any]] | None = None,
    generation: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    now = timestamp_value(timestamp)
    normalized_type = str(artifact_type or "").strip()
    return {
        "artifact_id": str(artifact_id or uuid.uuid4().hex),
        "type": normalized_type,
        "title": str(title or artifact_label(normalized_type)).strip(),
        "status": _normalize_status(status),
        "prompt": str(prompt or ""),
        "source_scope": normalize_source_scope(source_scope),
        "payload": deepcopy(payload),
        "citations": _normalize_records(citations),
        "exports": _normalize_records(exports),
        "generation": _normalize_generation(generation),
        "created_at": now,
        "updated_at": now,
    }


def normalize_artifact(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    artifact_type = str(value.get("type") or "artifact").strip()
    created_at = timestamp_value(str(value.get("created_at") or ""))
    return {
        "artifact_id": str(value.get("artifact_id") or uuid.uuid4().hex),
        "type": artifact_type,
        "title": str(value.get("title") or artifact_label(artifact_type)).strip(),
        "status": _normalize_status(value.get("status", ARTIFACT_STATUS_READY)),
        "prompt": str(value.get("prompt") or ""),
        "source_scope": normalize_source_scope(value.get("source_scope")),
        "payload": deepcopy(value.get("payload")),
        "citations": _normalize_records(value.get("citations")),
        "exports": _normalize_records(value.get("exports")),
        "generation": _normalize_generation(value.get("generation")),
        "created_at": created_at,
        "updated_at": timestamp_value(str(value.get("updated_at") or created_at)),
    }


def timestamp_value(value: str | None = None) -> str:
    return timestamp(value or None)


def _normalize_status(value: Any) -> str:
    status = str(value or ARTIFACT_STATUS_READY).strip()
    return status if status in ARTIFACT_STATUSES else ARTIFACT_STATUS_READY


def _normalize_records(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [deepcopy(item) for item in values if isinstance(item, dict)]


def _normalize_generation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"adapter": "legacy", "parameters": {}}
    adapter = str(value.get("adapter") or "unknown").strip() or "unknown"
    parameters = value.get("parameters")
    return {
        "adapter": adapter,
        "parameters": deepcopy(parameters if isinstance(parameters, dict) else {}),
        **{
            str(key): deepcopy(item)
            for key, item in value.items()
            if key not in {"adapter", "parameters"}
        },
    }


def _unique_text(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    output: list[str] = []
    seen: set[str] = set()
    for value in items:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output
