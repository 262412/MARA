from __future__ import annotations

from typing import Any

from ktem.docqa.artifact_models import ARTIFACT_LABELS

from .chat_docqa_runtime import build_web_docqa_request

STUDIO_ARTIFACT_TYPE_CHOICES = tuple(ARTIFACT_LABELS)
STUDIO_ARTIFACT_FORMAT_CHOICES = ("markdown", "json", "html", "csv", "pptx")


def build_studio_artifact_prompt(
    artifact_type: str,
    *,
    prompt: str = "",
    output_format: str = "markdown",
    difficulty: str = "",
    count: Any = None,
    language: str | None = None,
    note_records: list[dict[str, Any]] | None = None,
) -> str:
    label = ARTIFACT_LABELS.get(artifact_type, artifact_type.replace("_", " "))
    parts = [
        str(prompt or "").strip() or f"Generate a source-grounded {label}.",
        f"Preferred format: {str(output_format or 'markdown').strip()}.",
    ]
    language_text = str(language or "").strip()
    difficulty_text = str(difficulty or "").strip()
    count_value = _positive_int(count)
    if language_text:
        parts.append(f"Language: {language_text}.")
    if difficulty_text:
        parts.append(f"Difficulty: {difficulty_text}.")
    if count_value is not None:
        parts.append(f"Requested item count: {count_value}.")
    if note_records:
        parts.append("Notebook notes:")
        parts.extend(_note_prompt_lines(note_records))
    return "\n".join(parts)


def run_studio_artifact_turn(
    docqa_runtime: Any,
    *,
    artifact_type: str,
    prompt: str,
    output_format: str,
    difficulty: str,
    count: Any,
    conversation_id: str,
    chat_history: list | None,
    selected_inputs: dict[int, Any],
    settings: dict | None,
    reasoning_type: str | None,
    llm_type: str | None,
    use_mindmap: bool | str | None,
    use_citation: str | None,
    language: str | None,
    chat_state: dict | None,
    command_state: str | None,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    page_number: Any,
    qa_scope: str,
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
    note_ids: Any = None,
) -> Any:
    normalized_type = str(artifact_type or "").strip()
    if normalized_type not in ARTIFACT_LABELS:
        raise ValueError(f"Unknown Studio artifact type '{normalized_type}'.")

    selected_note_ids = _split_note_ids(note_ids)
    note_records = _notebook_note_records(conversation_id, selected_note_ids)
    request = build_web_docqa_request(
        prompt=build_studio_artifact_prompt(
            normalized_type,
            prompt=prompt,
            output_format=output_format,
            difficulty=difficulty,
            count=count,
            language=language,
            note_records=note_records,
        ),
        conversation_id=str(conversation_id or "").strip(),
        history=list(chat_history or []),
        selected_inputs=selected_inputs,
        settings=settings,
        reasoning_type=reasoning_type,
        llm=llm_type,
        use_mindmap=use_mindmap,
        use_citation=use_citation,
        language=language,
        state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        page_number=page_number,
        qa_scope=str(qa_scope or "page").replace("-", "_"),
        selected_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        task_type=normalized_type,
        agent_mode="auto",
        artifact_type=normalized_type,
        note_ids=selected_note_ids,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )
    return docqa_runtime.run_turn(request)


def run_studio_artifact_regenerate_turn(
    docqa_runtime: Any,
    *,
    artifact: dict[str, Any],
    fallback_source_ids: list[str],
    conversation_id: str,
    chat_history: list | None,
    selected_inputs: dict[int, Any],
    settings: dict | None,
    reasoning_type: str | None,
    llm_type: str | None,
    use_mindmap: bool | str | None,
    use_citation: str | None,
    language: str | None,
    chat_state: dict | None,
    command_state: str | None,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
) -> Any:
    artifact_type = _artifact_type(artifact)
    source_scope = _source_scope(artifact)
    source_ids = _source_ids(source_scope, fallback_source_ids)
    note_ids = _split_note_ids(source_scope.get("note_ids", []))
    if not source_ids:
        raise ValueError("Latest artifact does not have source scope.")

    request = build_web_docqa_request(
        prompt=_regenerate_prompt(artifact, artifact_type),
        conversation_id=str(conversation_id or "").strip(),
        history=list(chat_history or []),
        selected_file_ids=source_ids,
        selected_inputs=selected_inputs,
        settings=settings,
        reasoning_type=reasoning_type,
        llm=llm_type,
        use_mindmap=use_mindmap,
        use_citation=use_citation,
        language=language,
        state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        page_number=source_scope.get("page") or 1,
        qa_scope=str(source_scope.get("mode") or "document").replace("-", "_"),
        selected_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        task_type=artifact_type,
        agent_mode="auto",
        artifact_type=artifact_type,
        note_ids=note_ids,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )
    return docqa_runtime.run_turn(request)


def _positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    count = int(value)
    return count if count > 0 else None


def _split_note_ids(value: Any) -> list[str]:
    values = value if isinstance(value, list) else str(value or "").split(",")
    output: list[str] = []
    for item in values:
        note_id = str(item or "").strip()
        if note_id and note_id not in output:
            output.append(note_id)
    return output


def _notebook_note_records(
    conversation_id: str,
    note_ids: list[str],
) -> list[dict[str, Any]]:
    if not note_ids:
        return []
    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(str(conversation_id or "").strip())
    notes = [item for item in notebook.get("notes", []) if isinstance(item, dict)]
    by_id = {str(item.get("note_id") or ""): item for item in notes}
    missing = [note_id for note_id in note_ids if note_id not in by_id]
    if missing:
        raise ValueError("Notebook note does not exist: " + ", ".join(missing))
    return [dict(by_id[note_id]) for note_id in note_ids]


def _note_prompt_lines(note_records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for note in note_records:
        note_id = str(note.get("note_id") or "").strip()
        title = str(note.get("title") or "Notebook note").strip()
        text = str(note.get("text") or "").strip()
        lines.append(f"- {title} ({note_id}): {text}")
    return lines


def _artifact_type(artifact: dict[str, Any]) -> str:
    artifact_type = str(artifact.get("type") or "").strip()
    if artifact_type not in ARTIFACT_LABELS:
        raise ValueError("Latest artifact has an unknown type.")
    return artifact_type


def _source_scope(artifact: dict[str, Any]) -> dict[str, Any]:
    scope = artifact.get("source_scope")
    return dict(scope) if isinstance(scope, dict) else {}


def _source_ids(scope: dict[str, Any], fallback_source_ids: list[str]) -> list[str]:
    values = scope.get("source_ids") or fallback_source_ids
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _regenerate_prompt(artifact: dict[str, Any], artifact_type: str) -> str:
    prompt = str(artifact.get("prompt") or "").strip()
    if prompt:
        return prompt
    label = ARTIFACT_LABELS.get(artifact_type, artifact_type.replace("_", " "))
    return f"Regenerate a source-grounded {label}."
