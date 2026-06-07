from __future__ import annotations

from typing import Any

import click

from . import docqa_notebook_cli as notebook_cli
from .docqa_artifact_evaluate_cli import register_artifact_evaluate_command
from .docqa_options import ARTIFACT_TYPES


def register_artifact_commands(docqa: click.Group) -> None:
    @docqa.group("artifacts", short_help="Manage generated artifacts")
    def artifacts_group():
        """Manage saved MARA study artifacts for a DocQA conversation."""

    @artifacts_group.command("list")
    @click.argument("conversation_id", required=True)
    @notebook_cli._json_option
    def artifacts_list(conversation_id, json_output):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        notebook = notebook_cli._notebook_service().get_notebook(conversation_id)
        artifacts = _notebook_artifacts(notebook)
        if json_output:
            notebook_cli._echo_json(artifacts)
            return
        if not artifacts:
            notebook_cli._echo_text("No artifacts.")
            return
        for artifact in artifacts:
            _print_artifact(artifact)

    _register_artifact_show_command(artifacts_group)
    _register_artifact_generate_command(artifacts_group)
    _register_artifact_export_command(artifacts_group)
    register_artifact_evaluate_command(artifacts_group)
    _register_artifact_delete_command(artifacts_group)
    _register_artifact_save_note_command(artifacts_group)
    _register_artifact_regenerate_command(artifacts_group)


def _print_artifact(artifact: dict[str, Any]) -> None:
    notebook_cli._echo_text(
        f"{artifact.get('artifact_id', '')}\t{artifact.get('type', '')}"
    )


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


def _register_artifact_show_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("show")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", required=True)
    @notebook_cli._json_option
    def artifacts_show(conversation_id, artifact_id, json_output):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        notebook = notebook_cli._notebook_service().get_notebook(conversation_id)
        artifact = _notebook_artifact(notebook, artifact_id)
        if artifact is None:
            raise click.ClickException(f"Artifact '{artifact_id}' does not exist.")
        if json_output:
            notebook_cli._echo_json(artifact)
            return
        from ktem.docqa.artifact_exports import render_artifact_markdown

        notebook_cli._echo_text(render_artifact_markdown(artifact))


def _register_artifact_generate_command(artifacts_group: click.Group) -> None:
    def artifacts_generate(
        conversation_id,
        artifact_type,
        prompt,
        file_refs,
        source_refs,
        qa_scope,
        page_number,
        note_ids,
        output_format,
        language,
        difficulty,
        count,
        agent_mode,
        json_output,
    ):
        _run_artifact_generate(
            conversation_id=conversation_id,
            artifact_type=artifact_type,
            prompt=prompt,
            file_refs=file_refs,
            source_refs=source_refs,
            qa_scope=qa_scope,
            page_number=page_number,
            note_ids=note_ids,
            output_format=output_format,
            language=language,
            difficulty=difficulty,
            count=count,
            agent_mode=agent_mode,
            json_output=json_output,
        )

    artifacts_group.command("generate")(_artifact_generate_options(artifacts_generate))


def _run_artifact_generate(
    *,
    conversation_id,
    artifact_type,
    prompt,
    file_refs,
    source_refs,
    qa_scope,
    page_number,
    note_ids,
    output_format,
    language,
    difficulty,
    count,
    agent_mode,
    json_output,
) -> None:
    runtime = notebook_cli._create_runtime()
    notebook_cli._require_session(runtime, conversation_id)
    service = notebook_cli._notebook_service()
    notebook = service.get_notebook(conversation_id)
    source_ids = _source_ids_for_generate(runtime, notebook, source_refs, file_refs)
    if not source_ids:
        raise click.ClickException("Select sources or pass --file before generating.")

    note_records = _artifact_note_records(notebook, note_ids)
    artifact_prompt = _artifact_prompt(
        artifact_type,
        prompt=prompt,
        output_format=output_format,
        language=language,
        difficulty=difficulty,
        count=count,
        note_records=note_records,
    )
    source_scope_input = {
        "mode": str(qa_scope or "document"),
        "source_ids": list(source_ids),
    }
    if page_number is not None:
        source_scope_input["page"] = page_number
    if note_records:
        source_scope_input["note_ids"] = [str(item["note_id"]) for item in note_records]
    source_scope = _normalize_source_scope(source_scope_input)
    before_count = len(_notebook_artifacts(notebook))
    response = notebook_cli._run_docqa_turn(
        runtime,
        prompt=artifact_prompt,
        conversation_id=conversation_id,
        selected_file_ids=source_ids,
        qa_scope=qa_scope,
        page_number=page_number,
        reasoning_type="mara",
        task_type=artifact_type,
        agent_mode=agent_mode,
        artifact_type=artifact_type,
        note_ids=[str(item["note_id"]) for item in note_records],
        language=language,
    )
    artifact = _new_or_captured_artifact(
        service,
        conversation_id,
        artifact_type,
        response,
        before_count,
        prompt=artifact_prompt,
        source_scope=source_scope,
    )
    if json_output:
        notebook_cli._echo_json(artifact)
        return
    _print_artifact(artifact)


def _artifact_generate_options(command):
    options = [
        click.argument("conversation_id", required=True),
        click.option(
            "--type",
            "artifact_type",
            required=True,
            type=click.Choice(ARTIFACT_TYPES),
            help="MARA Studio artifact type to generate.",
        ),
        click.option("--prompt", default="", help="Generation instruction."),
        click.option("--file", "file_refs", multiple=True),
        click.option(
            "--source",
            "source_refs",
            multiple=True,
            help="Restrict generation to one or more source ids or names.",
        ),
        click.option(
            "--scope",
            "qa_scope",
            default="document",
            type=click.Choice(["page", "document", "multi-document"]),
            show_default=True,
            help="Artifact source scope.",
        ),
        click.option(
            "--page",
            "page_number",
            default=None,
            type=click.IntRange(min=1),
            help="Focus artifact generation on one page.",
        ),
        click.option(
            "--note",
            "note_ids",
            multiple=True,
            help="Notebook note id to include in the generation prompt.",
        ),
        click.option(
            "--format",
            "output_format",
            default="markdown",
            type=click.Choice(("markdown", "json", "html", "csv", "pptx")),
            show_default=True,
            help="Preferred output/export format for the artifact.",
        ),
        click.option("--language", default=None, help="Artifact language override."),
        click.option(
            "--difficulty", default=None, help="Quiz or flashcard difficulty."
        ),
        click.option(
            "--count",
            default=None,
            type=click.IntRange(min=1),
            help="Requested item count for list-like artifacts.",
        ),
        click.option(
            "--agent-mode",
            default="auto",
            type=click.Choice(("auto", "fast", "thorough")),
            show_default=True,
        ),
        notebook_cli._json_option,
    ]
    for option in reversed(options):
        command = option(command)
    return command


def _register_artifact_export_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("export")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", required=True)
    @click.option(
        "--format",
        "export_format",
        required=True,
        type=click.Choice(("md", "html", "json", "csv", "svg", "pptx", "mp3", "mp4")),
    )
    @click.option("--output", "output_path", default="", help="Export file path.")
    @notebook_cli._json_option
    def artifacts_export(
        conversation_id,
        artifact_id,
        export_format,
        output_path,
        json_output,
    ):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        service = notebook_cli._notebook_service()
        artifact = _required_artifact(service, conversation_id, artifact_id)
        output_path = output_path or f"{artifact_id}.{export_format}"
        try:
            exported_path = _export_artifact_to_path(
                artifact,
                export_format=export_format,
                output_path=output_path,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        exported = service.record_artifact_export_to_conversation(
            conversation_id,
            artifact_id,
            export_format=export_format,
            path=str(exported_path),
        )
        payload = {
            "conversation_id": conversation_id,
            "artifact_id": artifact_id,
            "format": export_format,
            "output_path": str(exported_path),
            "artifact": exported,
        }
        if json_output:
            notebook_cli._echo_json(payload)
            return
        notebook_cli._echo_text(str(exported_path))


def _register_artifact_delete_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("delete")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", required=True)
    @notebook_cli._json_option
    def artifacts_delete(conversation_id, artifact_id, json_output):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        try:
            deleted = (
                notebook_cli._notebook_service().delete_artifact_from_conversation(
                    conversation_id,
                    artifact_id,
                )
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        payload = {
            "conversation_id": conversation_id,
            "artifact_id": artifact_id,
            "deleted": deleted,
        }
        if json_output:
            notebook_cli._echo_json(payload)
            return
        notebook_cli._echo_text(f"Deleted artifact: {artifact_id}")


def _register_artifact_save_note_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("save-note")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", required=True)
    @notebook_cli._json_option
    def artifacts_save_note(conversation_id, artifact_id, json_output):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        service = notebook_cli._notebook_service()
        artifact = _required_artifact(service, conversation_id, artifact_id)
        fields = _build_artifact_note_fields(artifact)
        note = service.save_answer_note_to_conversation(
            conversation_id,
            title=fields["title"],
            answer=fields["text"],
            citation_refs=fields["citation_refs"],
        )
        payload = {
            "conversation_id": conversation_id,
            "artifact_id": artifact_id,
            "note": note,
        }
        if json_output:
            notebook_cli._echo_json(payload)
            return
        notebook_cli._echo_text(f"Saved artifact note: {note.get('note_id', '')}")


def _register_artifact_regenerate_command(artifacts_group: click.Group) -> None:
    @artifacts_group.command("regenerate")
    @click.argument("conversation_id", required=True)
    @click.option("--artifact", "artifact_id", required=True)
    @notebook_cli._json_option
    def artifacts_regenerate(conversation_id, artifact_id, json_output):
        runtime = notebook_cli._create_runtime()
        notebook_cli._require_session(runtime, conversation_id)
        service = notebook_cli._notebook_service()
        notebook = service.get_notebook(conversation_id)
        artifact = _required_artifact(service, conversation_id, artifact_id)
        artifact_type = str(artifact.get("type") or "").strip()
        source_scope = _normalize_source_scope(artifact.get("source_scope") or {})
        source_ids = list(source_scope.get("source_ids") or [])
        if not source_ids:
            source_ids = list(notebook.get("selected_source_ids") or [])
        if not source_ids:
            raise click.ClickException("Artifact does not have source scope.")

        before_count = len(_notebook_artifacts(notebook))
        prompt = str(artifact.get("prompt") or "").strip()
        note_ids = list(source_scope.get("note_ids") or [])
        response = notebook_cli._run_docqa_turn(
            runtime,
            prompt=prompt
            or f"Regenerate a source-grounded {artifact_type.replace('_', ' ')}.",
            conversation_id=conversation_id,
            selected_file_ids=source_ids,
            qa_scope=str(source_scope.get("mode") or "document"),
            page_number=source_scope.get("page"),
            reasoning_type="mara",
            task_type=artifact_type,
            agent_mode="auto",
            artifact_type=artifact_type,
            note_ids=note_ids,
        )
        regenerated = _new_or_captured_artifact(
            service,
            conversation_id,
            artifact_type,
            response,
            before_count,
            prompt=prompt,
            source_scope=source_scope,
        )
        payload = {
            "conversation_id": conversation_id,
            "artifact_id": artifact_id,
            "type": artifact_type,
            "regenerated": regenerated,
        }
        if json_output:
            notebook_cli._echo_json(payload)
            return
        notebook_cli._echo_text(f"Regenerated artifact: {artifact_id}")


def _source_ids_for_generate(runtime, notebook, source_refs, file_refs) -> list[str]:
    refs = list(source_refs or file_refs)
    if refs:
        return [record.file_id for record in runtime.resolve_file_refs(list(refs))]
    return list(notebook.get("selected_source_ids", []))


def _artifact_note_records(notebook: dict[str, Any], note_ids) -> list[dict[str, Any]]:
    lookup = [str(item or "").strip() for item in note_ids or [] if item]
    if not lookup:
        return []
    notes = [item for item in notebook.get("notes", []) if isinstance(item, dict)]
    by_id = {str(item.get("note_id") or ""): item for item in notes}
    missing = [note_id for note_id in lookup if note_id not in by_id]
    if missing:
        raise click.ClickException(
            "Notebook note does not exist: " + ", ".join(missing)
        )
    return [dict(by_id[note_id]) for note_id in lookup]


def _new_or_captured_artifact(
    service,
    conversation_id: str,
    artifact_type: str,
    response: Any,
    before_count: int,
    **metadata: Any,
) -> dict[str, Any]:
    artifacts = _notebook_artifacts(service.get_notebook(conversation_id))
    if len(artifacts) > before_count:
        return artifacts[-1]
    payload = getattr(response, "artifact", None)
    if payload is None:
        raise click.ClickException("MARA did not return an artifact.")
    return service.save_artifact_to_conversation(
        conversation_id,
        artifact_type=artifact_type,
        payload=payload,
        **metadata,
    )


def _normalize_source_scope(value: Any) -> dict[str, Any]:
    from ktem.docqa.artifact_models import normalize_source_scope

    return normalize_source_scope(value)


def _required_artifact(
    service, conversation_id: str, artifact_id: str
) -> dict[str, Any]:
    notebook = service.get_notebook(conversation_id)
    artifact = _notebook_artifact(notebook, artifact_id)
    if artifact is None:
        raise click.ClickException(f"Artifact '{artifact_id}' does not exist.")
    return artifact


def _export_artifact_to_path(artifact, *, export_format, output_path):
    from ktem.docqa.artifact_exports import export_artifact_to_path

    return export_artifact_to_path(
        artifact,
        export_format=export_format,
        output_path=output_path,
    )


def _build_artifact_note_fields(artifact):
    from ktem.docqa.artifact_service import build_artifact_note_fields

    return build_artifact_note_fields(artifact)


def _artifact_prompt(
    artifact_type: str,
    *,
    prompt: str,
    output_format: str,
    language: str | None,
    difficulty: str | None,
    count: int | None,
    note_records: list[dict[str, Any]],
) -> str:
    parts = [
        prompt.strip()
        or f"Generate a source-grounded {artifact_type.replace('_', ' ')}.",
        f"Preferred format: {output_format}.",
    ]
    if language:
        parts.append(f"Language: {language}.")
    if difficulty:
        parts.append(f"Difficulty: {difficulty}.")
    if count:
        parts.append(f"Requested item count: {count}.")
    if note_records:
        parts.append("Notebook notes:")
        parts.extend(_artifact_note_prompt_lines(note_records))
    return "\n".join(parts)


def _artifact_note_prompt_lines(note_records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for note in note_records:
        note_id = str(note.get("note_id") or "").strip()
        title = str(note.get("title") or "Notebook note").strip()
        text = str(note.get("text") or "").strip()
        lines.append(f"- {title} ({note_id}): {text}")
    return lines
