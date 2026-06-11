from __future__ import annotations

from typing import Any

from ktem.docqa.artifact_models import ARTIFACT_LABELS

from .chat_docqa_runtime import build_web_docqa_request
from .studio_artifact_parameters import build_parameterized_artifact_prompt

STUDIO_ARTIFACT_TYPE_CHOICES = tuple(
    artifact_type
    for artifact_type in ARTIFACT_LABELS
    if artifact_type != "custom_report"
)


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
    return build_parameterized_artifact_prompt(
        artifact_type,
        prompt=prompt,
        output_format=output_format,
        difficulty=difficulty,
        count=count,
        language=language,
        note_records=note_records,
    )


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
        selected_file_ids=selected_source_ids_for_studio_artifact(
            active_file_id,
            selected_inputs,
        ),
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


def selected_source_ids_for_studio_artifact(
    active_file_id: Any,
    selected_inputs: dict[int, Any] | None,
) -> list[str]:
    values: list[str] = []
    active_id = str(active_file_id or "").strip()
    if active_id:
        values.append(active_id)
    for selected_input in dict(selected_inputs or {}).values():
        values.extend(_selected_source_values(selected_input))
    return _unique_text(values)


def _selected_source_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        if value and _selector_mode(value[0]):
            return _selected_source_values(value[1]) if len(value) > 1 else []
        values: list[str] = []
        for item in value:
            values.extend(_selected_source_values(item))
        return values
    if isinstance(value, dict):
        for key in ("file_id", "source_id", "id"):
            if key in value:
                return _selected_source_values(value.get(key))
        return []
    text = str(value or "").strip()
    if (
        not text
        or _selector_mode(text)
        or (text.startswith("[") and text.endswith("]"))
    ):
        return []
    return [text]


def _selector_mode(value: Any) -> bool:
    return str(value or "").strip().lower() in {"select", "upload", "all"}


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
    return _unique_text(values)


def _unique_text(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or []:
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
