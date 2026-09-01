from __future__ import annotations

from typing import Any

_TASK_KEYWORDS = {
    "study_guide": ("study guide", "study-guide"),
    "flashcards": ("flashcard", "flash card"),
    "slide_outline": ("slide outline", "deck outline", "presentation outline"),
    "mindmap": ("mind map", "mindmap"),
    "quiz": ("quiz", "questions"),
    "summary": ("summary", "summarize", "summarise", "overview"),
    "compare": ("compare", "contrast", "difference", "differences"),
    "explain": ("explain", "why", "how does"),
}
_MODALITY_KEYWORDS = {
    "table": ("table", "row", "column", "spreadsheet", "csv"),
    "figure": ("figure", "image", "diagram", "chart", "plot"),
    "formula": ("formula", "equation", "math", "latex"),
    "slide": ("slide", "deck", "presentation", "ppt", "pptx"),
}
_VALID_TASK_TYPES = {
    "qa",
    "summary",
    "compare",
    "explain",
    "study_guide",
    "quiz",
    "flashcards",
    "mindmap",
    "slide_outline",
}


def understand_query(
    query: str,
    *,
    task_type: str | None = None,
    modality: str | None = None,
    qa_scope: str | None = None,
    active_file_id: str | None = None,
    page_number: int | None = None,
) -> dict[str, Any]:
    normalized = str(query or "").lower()
    detected_task = _detect_task_type(normalized, task_type)
    modalities = _requested_modalities(modality) or _detect_modalities(normalized)
    scope = _detect_scope(normalized, qa_scope, active_file_id, page_number)
    return {
        "question": query,
        "task_type": detected_task,
        "modalities": modalities,
        "scope": scope,
    }


def with_selected_source_context(
    understanding: dict[str, Any],
    source: Any,
) -> dict[str, Any]:
    selected_text = str(getattr(source, "selected_text", "") or "").strip()
    active_file_id = str(getattr(source, "active_file_id", "") or "").strip()
    page_number = getattr(source, "page_number", None)
    selected_file_ids = [
        str(file_id).strip()
        for file_id in getattr(source, "selected_file_ids", None) or []
        if str(file_id).strip()
    ]
    if not (
        selected_text
        or active_file_id
        or page_number not in (None, "")
        or len(selected_file_ids) == 1
    ):
        return understanding
    updated = dict(understanding)
    updated["selected_source_context"] = True
    source_ids = selected_file_ids or ([active_file_id] if active_file_id else [])
    if source_ids:
        updated["source_ids"] = source_ids
    if page_number not in (None, ""):
        updated["pages"] = [page_number]
    return updated


def plan_steps(
    understanding: dict[str, Any], *, agent_mode: str | None = None
) -> list[dict[str, str]]:
    mode = str(agent_mode or "auto").strip().lower()
    task_type = str(understanding.get("task_type") or "qa")
    scope = str(understanding.get("scope") or "document").replace("_", "-")
    modalities = [
        str(modality)
        for modality in understanding.get("modalities", ["text"])
        if modality
    ]
    if not modalities:
        modalities = ["text"]

    modality_text = ", ".join(modalities)
    plan = [
        {
            "tool": "source_retriever",
            "purpose": (
                f"Retrieve {modality_text} evidence for " f"{scope}-scoped {task_type}."
            ),
        }
    ]
    if mode == "fast":
        return plan

    for modality in modalities:
        if modality == "text":
            continue
        plan.append(
            {
                "tool": f"{modality}_inspector",
                "purpose": (
                    f"Inspect retrieved {modality} evidence before composing "
                    "the answer."
                ),
            }
        )
        if len(plan) >= 3:
            break

    if mode == "thorough":
        plan.append(
            {
                "tool": "claim_verifier",
                "purpose": "Check whether the answer is supported by retrieved evidence.",
            }
        )
    return plan[:4]


def _detect_task_type(normalized: str, task_type: str | None) -> str:
    normalized_task = str(task_type or "").strip().lower()
    if normalized_task in _VALID_TASK_TYPES:
        return normalized_task
    for candidate, keywords in _TASK_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return candidate
    return "qa"


def _detect_modalities(normalized: str) -> list[str]:
    modalities = [
        modality
        for modality, keywords in _MODALITY_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return modalities or ["text"]


def _requested_modalities(modality: str | None) -> list[str]:
    value = str(modality or "").strip().lower().replace("-", "_")
    if not value or value == "auto":
        return []
    return [value]


def _detect_scope(
    normalized: str,
    qa_scope: str | None,
    active_file_id: str | None,
    page_number: int | None,
) -> str:
    explicit_scope = str(qa_scope or "").strip().lower().replace("-", "_")
    if explicit_scope in {"page", "document", "multi_document"}:
        return explicit_scope
    if page_number is not None or "page " in normalized:
        return "page"
    if active_file_id:
        return "document"
    return "document"
