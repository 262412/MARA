from __future__ import annotations

import json
from typing import Any

import click


def _notebook_service():
    from ktem.docqa import _runtime_notebook

    return _runtime_notebook


def _create_runtime():
    from . import docqa_cli

    return docqa_cli.create_docqa_runtime()


def _run_docqa_turn(runtime: Any, **request_kwargs):
    from . import docqa_cli

    return docqa_cli._run_docqa_turn(runtime, **request_kwargs)


def _echo_json(payload: Any) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _echo_text(message: str) -> None:
    click.echo(message)


def _json_option(command):
    return click.option(
        "--json",
        "json_output",
        is_flag=True,
        default=False,
        show_default=True,
        help="Emit structured JSON output.",
    )(command)


def _require_session(runtime: Any, conversation_id: str):
    session = runtime.load_session(conversation_id)
    if session is None:
        raise click.ClickException(f"Conversation '{conversation_id}' does not exist.")
    return session


def _last_answer(session: Any) -> str:
    messages = list(getattr(session, "messages", []) or [])
    for _prompt, answer in reversed(messages):
        text = str(answer or "").strip()
        if text:
            return text
    raise click.ClickException("Conversation does not have an answer to save.")


def _last_citation_refs(session: Any) -> list[str]:
    retrieval_messages = list(getattr(session, "retrieval_messages", []) or [])
    for item in reversed(retrieval_messages):
        text = str(item or "").strip()
        if text:
            return [text]
    return []


def _print_note(note: dict[str, Any]) -> None:
    _echo_text(f"{note.get('note_id', '')}\t{note.get('title', '')}")


def _print_artifact(artifact: dict[str, Any]) -> None:
    _echo_text(f"{artifact.get('artifact_id', '')}\t{artifact.get('type', '')}")


def _notebook_artifacts(notebook: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = notebook.get("artifacts", [])
    return [dict(item) for item in artifacts if isinstance(item, dict)]


def _notebook_artifact(
    notebook: dict[str, Any],
    artifact_id: str,
) -> dict[str, Any] | None:
    lookup = str(artifact_id or "").strip()
    for artifact in _notebook_artifacts(notebook):
        if str(artifact.get("artifact_id") or "") == lookup:
            return artifact
    return None


def _find_note(notebook: dict[str, Any], note_id: str) -> dict[str, Any]:
    lookup = str(note_id or "").strip()
    for note in notebook.get("notes", []):
        if str(note.get("note_id") or "") == lookup:
            return dict(note)
    raise click.ClickException(f"Note '{note_id}' does not exist.")


def _runtime_source_ids(runtime: Any) -> list[str]:
    file_index = getattr(runtime, "file_index", None)
    list_source_ids = getattr(file_index, "list_source_ids", None)
    if not callable(list_source_ids):
        return []
    return [
        str(item or "").strip()
        for item in list_source_ids(getattr(runtime, "user_id", None))
        if str(item or "").strip()
    ]


def _result_source_ids(result: Any) -> list[str]:
    source_ids: list[str] = []
    for item in getattr(result, "successes", []):
        if isinstance(item, dict):
            source_id = str(item.get("source_id") or "").strip()
            if source_id:
                source_ids.append(source_id)
    return source_ids


def _indexed_source_ids(before: list[str], after: list[str], result: Any) -> list[str]:
    before_set = set(before)
    merged = [
        *_result_source_ids(result),
        *[item for item in after if item not in before_set],
    ]
    selected: list[str] = []
    seen: set[str] = set()
    for item in merged:
        if item in seen:
            continue
        seen.add(item)
        selected.append(item)
    return selected


def register_docqa_notebook_commands(docqa: click.Group) -> None:
    _register_notes_commands(docqa)
    _register_sources_commands(docqa)
    _register_artifact_commands(docqa)


def _register_notes_commands(docqa: click.Group) -> None:
    @docqa.group("notes", short_help="Manage notebook notes")
    def notes_group():
        """Manage MARA notebook notes for a saved DocQA conversation."""

    @notes_group.command("list")
    @click.argument("conversation_id", required=True)
    @_json_option
    def notes_list(conversation_id, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        notes = _notebook_service().get_notebook(conversation_id)["notes"]
        if json_output:
            _echo_json(notes)
            return
        if not notes:
            _echo_text("No notes.")
            return
        for note in notes:
            _print_note(note)

    @notes_group.command("add")
    @click.argument("conversation_id", required=True)
    @click.option("--title", default="", help="Note title.")
    @click.option("--text", required=True, help="Note body text.")
    @_json_option
    def notes_add(conversation_id, title, text, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        note = _notebook_service().add_note_to_conversation(
            conversation_id,
            title=title,
            text=text,
        )
        if json_output:
            _echo_json(note)
            return
        _print_note(note)

    _register_note_conversion_command(notes_group)


def _register_note_conversion_command(notes_group: click.Group) -> None:
    @notes_group.command("convert-source")
    @click.argument("conversation_id", required=True)
    @click.option("--note", "note_id", required=True, help="Notebook note id.")
    @click.option(
        "--reindex",
        is_flag=True,
        default=False,
        show_default=True,
        help="Force reindex if the generated note source already exists.",
    )
    @_json_option
    def notes_convert_source(conversation_id, note_id, reindex, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        service = _notebook_service()
        note = _find_note(service.get_notebook(conversation_id), note_id)
        source_path = service.materialize_note_source(conversation_id, note)
        before_source_ids = _runtime_source_ids(runtime)
        result = runtime.index_paths([source_path], reindex=reindex)
        if result.failures:
            raise click.ClickException("Note source failed to index.")

        source_ids = _indexed_source_ids(
            before_source_ids,
            _runtime_source_ids(runtime),
            result,
        )
        updated_note = service.record_note_indexed_source_to_conversation(
            conversation_id,
            note_id,
            source_ids=source_ids,
            source_path=source_path,
        )
        payload = {
            "conversation_id": conversation_id,
            "note_id": note_id,
            "source_path": source_path,
            "source_ids": source_ids,
            "note": updated_note,
            "index_result": result.as_dict(),
        }
        if json_output:
            _echo_json(payload)
            return
        _echo_text(
            "Indexed note source: "
            + (", ".join(source_ids) if source_ids else source_path)
        )

    @notes_group.command("save-answer")
    @click.argument("conversation_id", required=True)
    @click.option("--title", default="Saved answer", help="Note title.")
    @_json_option
    def notes_save_answer(conversation_id, title, json_output):
        runtime = _create_runtime()
        session = _require_session(runtime, conversation_id)
        note = _notebook_service().save_answer_note_to_conversation(
            conversation_id,
            title=title,
            answer=_last_answer(session),
            citation_refs=_last_citation_refs(session),
        )
        if json_output:
            _echo_json(note)
            return
        _print_note(note)


def _register_sources_commands(docqa: click.Group) -> None:
    @docqa.group("sources", short_help="Manage selected sources")
    def sources_group():
        """Manage selected MARA notebook sources for a DocQA conversation."""

    @sources_group.command("list")
    @click.argument("conversation_id", required=True)
    @_json_option
    def sources_list(conversation_id, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        notebook = _notebook_service().get_notebook(conversation_id)
        if json_output:
            _echo_json(notebook)
            return
        selected = notebook["selected_source_ids"]
        _echo_text(
            "Selected sources: " + (", ".join(selected) if selected else "(none)")
        )

    @sources_group.command("select")
    @click.argument("conversation_id", required=True)
    @click.option("--file", "file_refs", multiple=True, required=True)
    @_json_option
    def sources_select(conversation_id, file_refs, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        records = runtime.resolve_file_refs(list(file_refs))
        selected = _notebook_service().select_conversation_sources(
            conversation_id,
            [record.file_id for record in records],
        )
        payload = {
            "conversation_id": conversation_id,
            "selected_source_ids": selected,
        }
        if json_output:
            _echo_json(payload)
            return
        _echo_text("Selected sources: " + ", ".join(selected))

    _register_source_guide_command(sources_group)


def _register_source_guide_command(sources_group: click.Group) -> None:
    @sources_group.command("guide")
    @click.argument("conversation_id", required=True)
    @click.option("--file", "file_refs", multiple=True)
    @_json_option
    def sources_guide(conversation_id, file_refs, json_output):
        runtime = _create_runtime()
        _require_session(runtime, conversation_id)
        service = _notebook_service()
        refs = list(file_refs)
        if not refs:
            refs = list(service.get_notebook(conversation_id)["selected_source_ids"])
        records = runtime.resolve_file_refs(refs) if refs else []
        guides = service.build_source_guides(records)
        if json_output:
            _echo_json(guides)
            return
        if not guides:
            _echo_text("No selected sources.")
            return
        for guide in guides:
            _echo_text(f"{guide['source_id']}\t{guide['name']}")
            _echo_text(f"  {guide['summary']}")


def _register_artifact_commands(docqa: click.Group) -> None:
    from .docqa_artifacts_cli import register_artifact_commands

    register_artifact_commands(docqa)
