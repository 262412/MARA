from __future__ import annotations

from typing import Any

from ktem.preview.errors import PreviewContextError, PreviewErrorCode


def resolve_active_source(
    preview: Any,
    selected_file_ids: list[str],
    active_file_id: str,
    active_file_name: str,
    *,
    user_id: Any,
) -> tuple[str, str]:
    if active_file_id and not active_file_name:
        active_file_name = preview.resolve_file_name(active_file_id, user_id=user_id)
    if not active_file_name:
        inferred_id, inferred_name, _ = preview.resolve_selected_file(
            selected_file_ids, user_id=user_id
        )
        active_file_id = active_file_id or inferred_id
        active_file_name = active_file_name or inferred_name
    return active_file_id, active_file_name


def resolve_page_text(
    preview: Any,
    qa_scope: str,
    page_number: int | None,
    active_file_id: str,
    active_file_name: str,
    selected_text: str,
    *,
    user_id: Any,
) -> str:
    if (
        qa_scope == "page"
        and not selected_text
        and page_number is not None
        and active_file_id
        and active_file_name
    ):
        selected_text = preview.get_page_context_text(
            active_file_id,
            active_file_name,
            page_number,
            user_id=user_id,
        )
    if qa_scope == "page" and not selected_text:
        raise _empty_page_context_error()
    return selected_text


def validate_sources(preview: Any, file_ids: list[str], *, user_id: Any) -> None:
    if file_ids:
        preview.resolve_sources(file_ids, user_id=user_id, strict=True)


def _empty_page_context_error() -> PreviewContextError:
    return PreviewContextError(
        PreviewErrorCode.CONTEXT_TEXT_UNAVAILABLE,
        stage="page_context",
        source_path="source-unavailable",
        converter="preview",
        details="No text is available for the requested DocQA page.",
    )
