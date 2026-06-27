from __future__ import annotations

import json
import re

import click

from .docqa_notebook_cli import register_docqa_notebook_commands
from .docqa_options import docqa_shared_options as _docqa_shared_options
from .docqa_output import print_docqa_response as _print_docqa_response
from .docqa_request import DocQARequest, to_runtime_docqa_request

_REPL_COMMANDS = (
    "Commands: /files, /use <file>, /page <n|clear>, /selected-text [text], "
    "/history, /help, /exit"
)


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
    return DocQARequest(**kwargs)


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


def _resolve_cli_files(runtime, file_refs):
    if not file_refs:
        return []
    return runtime.resolve_file_refs(list(file_refs))


def _resolve_cli_active_file(runtime, active_file_ref):
    if not active_file_ref:
        return None
    matches = runtime.resolve_file_refs([active_file_ref])
    return matches[0] if matches else None


def _run_docqa_turn(runtime, **request_kwargs):
    request_kwargs["qa_scope"] = str(request_kwargs.get("qa_scope") or "auto").replace(
        "-", "_"
    )
    request = _create_docqa_request(**request_kwargs)
    return runtime.run_turn(to_runtime_docqa_request(request))


def _run_docqa_ask_turn(runtime, options):
    selected_records = _resolve_cli_files(runtime, options["file_refs"])
    active_record = _resolve_cli_active_file(runtime, options["active_file"])

    return _run_docqa_turn(
        runtime,
        prompt=options["prompt"],
        conversation_id=options["conversation"] or "",
        selected_file_ids=[record.file_id for record in selected_records]
        if options["file_refs"]
        else None,
        active_file_id=active_record.file_id if active_record else "",
        active_file_name=active_record.name if active_record else "",
        qa_scope=options["qa_scope"],
        page_number=options["page"],
        selected_text=options["selected_text"] or "",
        graph_context=parse_graph_context_file(options["graph_context_file"]),
        reasoning_type=options["reasoning"],
        task_type=options["task_type"],
        agent_mode=options["agent_mode"],
        artifact_type=options["artifact_type"],
        controller_mode=options["controller_mode"],
        route_policy=options["route_policy"],
        planner_backend=options["planner_backend"],
        planner_model=options["planner_model"],
        allowed_routes=list(options["allowed_routes"] or []),
        verification_mode=options["verification_mode"],
        verification_domain=options["verification_domain"],
        max_context_length=options["max_context_length"],
        llm=options["llm"],
        visual_retriever_backend=options["visual_retriever_backend"],
        visual_generator_backend=options["visual_generator_backend"],
        use_mindmap=options["mindmap"],
        use_citation=options["citation"],
        language=options["language"],
    )


def _print_repl_history(runtime, conversation_id):
    latest = runtime.load_session(conversation_id)
    if not latest or not latest.messages:
        _echo_text("No messages yet.")
        return
    for index, (question, answer) in enumerate(latest.messages, start=1):
        _echo_text(f"[{index}] Q: {question}")
        _echo_text(f"[{index}] A: {answer}")


def _run_docqa_repl(
    runtime,
    conversation_id,
    file_refs=(),
    active_file_ref="",
    page=None,
    qa_scope="auto",
    selected_text="",
    graph_context_file="",
    reasoning=None,
    task_type=None,
    agent_mode=None,
    artifact_type=None,
    controller_options=None,
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
    request_overrides = {
        "graph_context": graph_context,
        "reasoning_type": reasoning,
        "task_type": task_type,
        "agent_mode": agent_mode,
        "artifact_type": artifact_type,
        "llm": llm,
        "use_mindmap": mindmap,
        "use_citation": citation,
        "language": language,
    }
    request_overrides.update(dict(controller_options or {}))

    _echo_text(f"Conversation: {conversation_id}")
    _echo_text(_REPL_COMMANDS)

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
            _echo_text(_REPL_COMMANDS)
            continue
        if prompt == "/files":
            _print_file_records(
                runtime.list_files(),
                selected_ids=selected_file_ids_override or session.graph_source_ids,
            )
            continue
        if prompt.startswith("/use"):
            refs = [
                part
                for part in re.split(r"[,\s]+", prompt[len("/use") :].strip())
                if part
            ]
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
            _print_repl_history(runtime, conversation_id)
            continue

        response = _run_docqa_turn(
            runtime,
            prompt=prompt,
            conversation_id=conversation_id,
            selected_file_ids=selected_file_ids_override,
            active_file_id=active_file_id,
            active_file_name=active_file_name,
            qa_scope=qa_scope,
            page_number=current_page,
            selected_text=current_selected_text,
            **request_overrides,
        )
        conversation_id = response.conversation_id
        if json_output:
            _echo_payload_json(response.as_dict())
        else:
            _echo_text("")
            _print_docqa_response(response, _echo_text)
            _echo_text("")


@click.group()
def docqa():
    """Document QA CLI backed by the app's runtime/index/session data.

    Action guide:
    - Health check: `MARA docqa doctor`
    - Index documents: `MARA docqa index`
    - Inspect indexed files: `MARA docqa files`
    - Delete indexed files: `MARA docqa delete`
    - Ask one question: `MARA docqa ask`
    - Interactive chat: `MARA docqa chat`
    - Inspect saved sessions: `MARA docqa sessions`
    - Manage selected sources: `MARA docqa sources`
    - Manage notebook notes: `MARA docqa notes`
    - Manage generated artifacts: `MARA docqa artifacts`
    - Resume a conversation: `MARA docqa resume`
    - Maintainer acceptance check: `MARA docqa acceptance` or `MARA docqa check`

    Use the umbrella `MARA-docqa` surface for the DocQA mainline. The
    acceptance/check commands stay available under `MARA docqa`, but they are
    maintainer workflows rather than part of the focused MARA skill family.
    """


@docqa.command("doctor", short_help="Health check")
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
        _echo_text(f"Default embedding: {result['embedding_default'] or '(missing)'}")
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


@docqa.command("acceptance", short_help="Maintainer acceptance check")
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


@docqa.command("index", short_help="Index documents")
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


@docqa.command("files", short_help="Inspect indexed files")
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


@docqa.command("delete", short_help="Delete indexed files")
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


@docqa.command("sessions", short_help="Inspect saved sessions")
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


@docqa.command("ask", short_help="Ask one question")
@click.option("--prompt", required=True, help="Question to ask.")
@_docqa_shared_options
def docqa_ask(
    prompt,
    conversation,
    file_refs,
    active_file,
    page,
    qa_scope,
    selected_text,
    graph_context_file,
    reasoning,
    task_type,
    agent_mode,
    artifact_type,
    controller_mode,
    route_policy,
    planner_backend,
    planner_model,
    allowed_routes,
    verification_mode,
    verification_domain,
    max_context_length,
    llm,
    visual_retriever_backend,
    visual_generator_backend,
    citation,
    language,
    mindmap,
    json_output,
):
    """Run one DocQA turn and persist it to a conversation.

    Use `--file` to scope retrieval, `--page` for page-level QA, and
    `--selected-text` for snippet-focused QA.

    Whole-document QA:
    `MARA docqa ask --file report.pdf --prompt "Summarize this document"`

    Page-level QA:
    `MARA docqa ask --file report.pdf --page 12 --prompt "What does this page say?"`

    Text-focused QA:
    `MARA docqa ask --file report.pdf --selected-text "contract termination clause" --prompt "Explain this section"`
    """
    options = dict(locals())
    json_output = options.pop("json_output")
    response = _run_docqa_ask_turn(create_docqa_runtime(), options)

    if json_output:
        _echo_payload_json(response.as_dict())
        return

    _print_docqa_response(response, _echo_text)


@docqa.command("chat", short_help="Interactive chat")
@_docqa_shared_options
def docqa_chat(
    conversation,
    file_refs,
    active_file,
    page,
    qa_scope,
    selected_text,
    graph_context_file,
    reasoning,
    task_type,
    agent_mode,
    artifact_type,
    controller_mode,
    route_policy,
    planner_backend,
    planner_model,
    allowed_routes,
    verification_mode,
    verification_domain,
    max_context_length,
    llm,
    visual_retriever_backend,
    visual_generator_backend,
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
        qa_scope=qa_scope,
        selected_text=selected_text,
        graph_context_file=graph_context_file,
        reasoning=reasoning,
        task_type=task_type,
        agent_mode=agent_mode,
        artifact_type=artifact_type,
        controller_options={
            "controller_mode": controller_mode,
            "route_policy": route_policy,
            "planner_backend": planner_backend,
            "planner_model": planner_model,
            "allowed_routes": list(allowed_routes or []),
            "verification_mode": verification_mode,
            "verification_domain": verification_domain,
            "max_context_length": max_context_length,
            "visual_retriever_backend": visual_retriever_backend,
            "visual_generator_backend": visual_generator_backend,
        },
        llm=llm,
        citation=citation,
        language=language,
        mindmap=mindmap,
        json_output=json_output,
    )


@docqa.command("resume", short_help="Resume a conversation")
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
    _run_docqa_repl(
        runtime=runtime, conversation_id=conversation_id, json_output=json_output
    )


register_docqa_notebook_commands(docqa)
main = docqa
