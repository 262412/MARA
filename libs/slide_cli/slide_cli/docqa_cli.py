from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import click


@dataclass
class _DocQARequest:
    prompt: str
    conversation_id: str = ""
    selected_file_ids: list[str] | None = None
    selected_inputs: dict[int, Any] | None = None
    active_file_id: str = ""
    active_file_name: str = ""
    page_number: int | None = None
    selected_text: str = ""
    graph_context: dict[str, Any] = field(default_factory=dict)
    graph_source_ids: list[str] | None = None
    settings: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    history: list[tuple[str, str]] | None = None
    reasoning_type: str | None = None
    llm: str | None = None
    use_mindmap: bool | str | None = None
    use_citation: str | None = None
    language: str | None = None
    command_state: str | None = None
    user_id: Any = None
    origin: str = "cli"


def _echo_json(payload):
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _echo_payload_json(payload):
    _echo_json(payload)


def _echo_text(message=""):
    text = "" if message is None else str(message)
    try:
        click.echo(text)
    except UnicodeEncodeError:
        click.echo(text.encode("ascii", errors="backslashreplace").decode("ascii"))


def create_docqa_runtime():
    from .docqa_runtime import create_docqa_runtime as _create_docqa_runtime

    return _create_docqa_runtime()


def collect_docqa_doctor_payload():
    from .docqa_runtime import (
        collect_docqa_doctor_payload as _collect_docqa_doctor_payload,
    )

    return _collect_docqa_doctor_payload()


def collect_docqa_file_records():
    from .docqa_runtime import collect_docqa_file_records as _collect_docqa_file_records

    return _collect_docqa_file_records()


def collect_docqa_session_summaries():
    from .docqa_runtime import (
        collect_docqa_session_summaries as _collect_docqa_session_summaries,
    )

    return _collect_docqa_session_summaries()


def parse_graph_context_file(graph_context_file: str):
    from .docqa_runtime import parse_graph_context_file as _parse_graph_context_file

    return _parse_graph_context_file(graph_context_file)


def run_docqa_acceptance_matrix(**kwargs):
    from .docqa_runtime import (
        run_docqa_acceptance_matrix as _run_docqa_acceptance_matrix,
    )

    return _run_docqa_acceptance_matrix(**kwargs)


def _create_docqa_request(**kwargs):
    return _DocQARequest(**kwargs)


def _print_docqa_response(response):
    _echo_text(f"Conversation: {response.conversation_id}")
    if response.active_file_name:
        page_suffix = f" | page {response.page_number}" if response.page_number else ""
        _echo_text(f"Active file: {response.active_file_name}{page_suffix}")
    _echo_text("")
    _echo_text(response.answer)
    if response.references_text:
        _echo_text("")
        _echo_text("Evidence:")
        _echo_text(response.references_text)


def _value(item, key, default=""):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _print_file_records(records, selected_ids=None):
    selected_ids = set(selected_ids or [])
    _echo_text("ID\tName\tTokens\tSize\tLoader")
    for record in records:
        record_id = str(_value(record, "file_id", "") or "")
        marker = "*" if record_id in selected_ids else ""
        _echo_text(
            f"{record_id}{marker}\t{_value(record, 'name', '')}\t{_value(record, 'tokens', 0)}\t{_value(record, 'size', 0)}\t{_value(record, 'loader', '')}"
        )


def _print_session_summaries(summaries):
    _echo_text("ID\tName\tMessages\tFiles\tOrigin")
    for summary in summaries:
        _echo_text(
            f"{_value(summary, 'conversation_id', '')}\t{_value(summary, 'name', '')}\t{_value(summary, 'message_count', 0)}\t{_value(summary, 'graph_source_count', 0)}\t{_value(summary, 'origin', '')}"
        )


def _print_docqa_acceptance_summary(payload):
    results = payload.get("results", [])
    coverage = sorted(
        {
            str(entry.get("name")).strip()
            for entry in results
            if str(entry.get("name") or "").strip()
        }
    )

    _echo_text(f"Status: {str(payload.get('status', 'unknown')).upper()}")
    _echo_text(f"Checks: {len(results)}")
    if payload.get("user_id"):
        _echo_text(f"User: {payload['user_id']}")
    if payload.get("work_dir"):
        _echo_text(f"Artifacts: {payload['work_dir']}")
    if coverage:
        _echo_text(f"Coverage: {', '.join(coverage)}")


def _docqa_shared_options(command):
    options = [
        click.option(
            "--conversation",
            default="",
            help="Existing conversation id to continue.",
        ),
        click.option(
            "--file",
            "file_refs",
            multiple=True,
            help="Restrict retrieval to one or more file ids or names.",
        ),
        click.option(
            "--active-file",
            default="",
            help="Active file id or name for page-level QA focus.",
        ),
        click.option(
            "--page",
            default=None,
            type=click.IntRange(min=1),
            help="Focus QA on one page. Omit to use whole-document QA.",
        ),
        click.option(
            "--selected-text",
            default="",
            help="Explicit selected text to focus retrieval without forcing page 1.",
        ),
        click.option(
            "--graph-context-file",
            default="",
            help="JSON file containing graph context to inject.",
        ),
        click.option(
            "--reasoning",
            default=None,
            help="Temporary reasoning override.",
        ),
        click.option(
            "--llm",
            default=None,
            help="Temporary LLM override.",
        ),
        click.option(
            "--citation",
            default=None,
            type=click.Choice(["highlight", "inline", "off"]),
            help="Citation mode override.",
        ),
        click.option(
            "--language",
            default=None,
            help="Response language override.",
        ),
        click.option(
            "--mindmap",
            flag_value=True,
            default=None,
            help="Enable mindmap output for this run.",
        ),
        click.option(
            "--json",
            "json_output",
            is_flag=True,
            default=False,
            show_default=True,
            help="Emit structured JSON output.",
        ),
    ]
    for option in reversed(options):
        command = option(command)
    return command


def _resolve_cli_files(runtime, file_refs):
    if not file_refs:
        return []
    return runtime.resolve_file_refs(list(file_refs))


def _resolve_cli_active_file(runtime, active_file_ref):
    if not active_file_ref:
        return None
    matches = runtime.resolve_file_refs([active_file_ref])
    return matches[0] if matches else None


def _run_docqa_repl(
    runtime,
    conversation_id,
    file_refs=(),
    active_file_ref="",
    page=None,
    selected_text="",
    graph_context_file="",
    reasoning=None,
    llm=None,
    citation=None,
    language=None,
    mindmap=None,
    json_output=False,
):
    session = runtime.load_session(conversation_id)
    if session is None:
        raise click.ClickException(f"Conversation '{conversation_id}' does not exist.")

    selected_file_ids_override = None
    if file_refs:
        selected_file_ids_override = [
            record.file_id for record in _resolve_cli_files(runtime, file_refs)
        ]

    active_record = _resolve_cli_active_file(runtime, active_file_ref)
    active_file_id = active_record.file_id if active_record else ""
    active_file_name = active_record.name if active_record else ""
    current_page = max(1, int(page)) if page not in (None, "") else None
    current_selected_text = str(selected_text or "").strip()
    graph_context = parse_graph_context_file(graph_context_file)

    _echo_text(f"Conversation: {conversation_id}")
    _echo_text(
        "Commands: /files, /use <file>, /page <n|clear>, /selected-text [text], /history, /help, /exit"
    )

    while True:
        try:
            prompt = click.prompt(
                "docqa", prompt_suffix="> ", show_default=False, default=""
            )
        except (EOFError, click.Abort):
            _echo_text("")
            break

        prompt = str(prompt or "").strip()
        if not prompt:
            continue

        if prompt == "/exit":
            break
        if prompt == "/help":
            _echo_text(
                "Commands: /files, /use <file>, /page <n|clear>, /selected-text [text], /history, /help, /exit"
            )
            continue
        if prompt == "/files":
            _print_file_records(
                runtime.list_files(),
                selected_ids=selected_file_ids_override or session.graph_source_ids,
            )
            continue
        if prompt.startswith("/use"):
            refs = [part for part in re.split(r"[,\s]+", prompt[len("/use") :].strip()) if part]
            if not refs:
                _echo_text("Usage: /use <file-id-or-name> [another-file]")
                continue
            matches = runtime.resolve_file_refs(refs)
            selected_file_ids_override = [record.file_id for record in matches]
            if matches:
                active_file_id = matches[0].file_id
                active_file_name = matches[0].name
            _echo_text(f"Using {len(matches)} file(s).")
            continue
        if prompt.startswith("/page"):
            value = prompt[len("/page") :].strip()
            if value.lower() in {"", "clear", "off", "document", "doc"}:
                current_page = None
                _echo_text("Page focus cleared. Using whole-document QA.")
                continue
            if not value.isdigit():
                _echo_text("Usage: /page <number> or /page clear")
                continue
            current_page = max(1, int(value))
            _echo_text(f"Page set to {current_page}.")
            continue
        if prompt.startswith("/selected-text"):
            current_selected_text = prompt[len("/selected-text") :].strip()
            if current_selected_text:
                _echo_text("Selected text updated.")
            else:
                _echo_text("Selected text cleared.")
            continue
        if prompt == "/history":
            latest = runtime.load_session(conversation_id)
            if not latest or not latest.messages:
                _echo_text("No messages yet.")
                continue
            for index, (question, answer) in enumerate(latest.messages, start=1):
                _echo_text(f"[{index}] Q: {question}")
                _echo_text(f"[{index}] A: {answer}")
            continue

        response = runtime.run_turn(
            _create_docqa_request(
                prompt=prompt,
                conversation_id=conversation_id,
                selected_file_ids=selected_file_ids_override,
                active_file_id=active_file_id,
                active_file_name=active_file_name,
                page_number=current_page,
                selected_text=current_selected_text,
                graph_context=graph_context,
                reasoning_type=reasoning,
                llm=llm,
                use_mindmap=mindmap,
                use_citation=citation,
                language=language,
            )
        )
        conversation_id = response.conversation_id
        if json_output:
            _echo_payload_json(response.as_dict())
        else:
            _echo_text("")
            _print_docqa_response(response)
            _echo_text("")


@click.group()
def docqa():
    """Document QA CLI backed by the app's runtime/index/session data.

    Action guide:
    - Health check: `slide docqa doctor` (platform skill: slide-docqa-doctor)
    - Index documents: `slide docqa index` (platform skill: slide-docqa-index)
    - Inspect indexed files: `slide docqa files` (platform skill: slide-docqa-files)
    - Delete indexed files: `slide docqa delete` (platform skill: slide-docqa-delete)
    - Ask one question: `slide docqa ask` (platform skill: slide-docqa-ask)
    - Interactive chat: `slide docqa chat` (platform skill: slide-docqa-chat)
    - Inspect saved sessions: `slide docqa sessions` (platform skill: slide-docqa-sessions)
    - Resume a conversation: `slide docqa resume` (platform skill: slide-docqa-resume)
    - Maintainer acceptance check: `slide docqa acceptance` or `slide docqa check`

    Use the umbrella `slide-docqa` surface for the DocQA mainline. The
    acceptance/check commands stay available under `slide docqa`, but they are
    maintainer workflows rather than part of the focused slide skill family.
    """


@docqa.command("doctor")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_doctor(json_output):
    result = collect_docqa_doctor_payload()

    if json_output:
        _echo_payload_json(result)
    else:
        _echo_text(f"Status: {'OK' if result['ok'] else 'FAIL'}")
        _echo_text(f"App: {result['app_name']}")
        _echo_text(f"Default user: {result['default_user_id']}")
        _echo_text(f"Index: {result['index_name'] or '(missing)'}")
        _echo_text(f"Default LLM: {result['llm_default'] or '(missing)'}")
        _echo_text(
            f"Default embedding: {result['embedding_default'] or '(missing)'}"
        )
        _echo_text(f"Indexed files: {result['file_count']}")
        _echo_text(f"Saved sessions: {result['session_count']}")
        if result["graph_cache_dir"]:
            _echo_text(f"Graph cache: {result['graph_cache_dir']}")
        for issue in result["issues"]:
            _echo_text(f"- {issue}")
        for warning in result["warnings"]:
            _echo_text(f"! {warning}")

    if not result["ok"]:
        raise click.ClickException("DocQA runtime is not healthy.")


@docqa.command("acceptance")
@click.option(
    "--keep-artifacts",
    is_flag=True,
    default=False,
    show_default=True,
    help="Keep the temporary sample files and install targets produced by the matrix.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    show_default=True,
    help="Show in-process logs and warnings from the acceptance matrix.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_acceptance(keep_artifacts, verbose, json_output):
    try:
        payload = run_docqa_acceptance_matrix(
            keep_artifacts=keep_artifacts,
            verbose=verbose,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_payload_json(payload)
        return

    _print_docqa_acceptance_summary(payload)


docqa.add_command(docqa_acceptance, "check")


@docqa.command("index")
@click.argument("paths", nargs=-1, required=True)
@click.option(
    "--reindex",
    is_flag=True,
    default=False,
    show_default=True,
    help="Force reindex for files that already exist.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_index(paths, reindex, json_output):
    runtime = create_docqa_runtime()
    result = runtime.index_paths(list(paths), reindex=reindex)

    if json_output:
        _echo_payload_json(result.as_dict())
    else:
        _echo_text(f"Indexed successfully: {len(result.successes)}")
        for item in result.successes:
            _echo_text(f"- {item.get('file_name') or item.get('file_path')}")
        if result.failures:
            _echo_text(f"Failed: {len(result.failures)}")
            for item in result.failures:
                _echo_text(
                    f"- {item.get('file_name') or item.get('file_path')}: {item.get('message', 'unknown error')}"
                )

    if result.failures:
        raise click.ClickException("Some inputs failed to index.")


@docqa.command("files")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_files(json_output):
    records = collect_docqa_file_records()

    if json_output:
        _echo_payload_json(records)
        return

    _print_file_records(records)


@docqa.command("delete")
@click.argument("refs", nargs=-1, required=True)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_delete(refs, json_output):
    runtime = create_docqa_runtime()
    deleted = runtime.delete_files(list(refs))

    if json_output:
        _echo_payload_json([record.as_dict() for record in deleted])
        return

    _echo_text(f"Deleted: {len(deleted)}")
    for record in deleted:
        _echo_text(f"- {record.name} ({record.file_id})")


@docqa.command("sessions")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def docqa_sessions(json_output):
    summaries = collect_docqa_session_summaries()

    if json_output:
        _echo_payload_json(summaries)
        return

    _print_session_summaries(summaries)


@docqa.command("ask")
@click.option("--prompt", required=True, help="Question to ask.")
@_docqa_shared_options
def docqa_ask(
    prompt,
    conversation,
    file_refs,
    active_file,
    page,
    selected_text,
    graph_context_file,
    reasoning,
    llm,
    citation,
    language,
    mindmap,
    json_output,
):
    """Run one DocQA turn and persist it to a conversation.

    Use `--file` to scope retrieval, `--page` for page-level QA, and
    `--selected-text` for snippet-focused QA.

    Whole-document QA:
    `slide docqa ask --file report.pdf --prompt "Summarize this document"`

    Page-level QA:
    `slide docqa ask --file report.pdf --page 12 --prompt "What does this page say?"`

    Text-focused QA:
    `slide docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"`
    """
    runtime = create_docqa_runtime()
    selected_records = _resolve_cli_files(runtime, file_refs)
    active_record = _resolve_cli_active_file(runtime, active_file)

    response = runtime.run_turn(
        _create_docqa_request(
            prompt=prompt,
            conversation_id=conversation or "",
            selected_file_ids=[record.file_id for record in selected_records]
            if file_refs
            else None,
            active_file_id=active_record.file_id if active_record else "",
            active_file_name=active_record.name if active_record else "",
            page_number=page,
            selected_text=selected_text or "",
            graph_context=parse_graph_context_file(graph_context_file),
            reasoning_type=reasoning,
            llm=llm,
            use_mindmap=mindmap,
            use_citation=citation,
            language=language,
        )
    )

    if json_output:
        _echo_payload_json(response.as_dict())
        return

    _print_docqa_response(response)


@docqa.command("chat")
@_docqa_shared_options
def docqa_chat(
    conversation,
    file_refs,
    active_file,
    page,
    selected_text,
    graph_context_file,
    reasoning,
    llm,
    citation,
    language,
    mindmap,
    json_output,
):
    """Open an interactive DocQA REPL backed by saved conversation state.

    Use `/help` inside the session for REPL commands such as `/files`, `/use`,
    `/page <n|clear>`, `/selected-text [text]`, and `/history`.
    """
    runtime = create_docqa_runtime()
    if conversation:
        session = runtime.load_session(conversation)
        if session is None:
            raise click.ClickException(f"Conversation '{conversation}' does not exist.")
    else:
        session = runtime.create_session()

    _run_docqa_repl(
        runtime=runtime,
        conversation_id=session.conversation_id,
        file_refs=file_refs,
        active_file_ref=active_file,
        page=page,
        selected_text=selected_text,
        graph_context_file=graph_context_file,
        reasoning=reasoning,
        llm=llm,
        citation=citation,
        language=language,
        mindmap=mindmap,
        json_output=json_output,
    )


@docqa.command("resume")
@click.argument("conversation_id", required=True)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output for each REPL answer.",
)
def docqa_resume(conversation_id, json_output):
    """Resume an existing conversation in the interactive DocQA REPL."""
    runtime = create_docqa_runtime()
    _run_docqa_repl(runtime=runtime, conversation_id=conversation_id, json_output=json_output)


main = docqa


__all__ = [
    "docqa",
    "main",
    "create_docqa_runtime",
    "run_docqa_acceptance_matrix",
]
