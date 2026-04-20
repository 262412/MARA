import json
import os
import re
import subprocess
import sys
from pathlib import Path

import click
import yaml
from trogon import tui


PLATFORM_CHOICES = ("claude-code", "codex")


# check if the output is not a .yml file -> raise error
def check_config_format(config):
    if os.path.exists(config):
        if isinstance(config, str):
            with open(config) as f:
                yaml.safe_load(f)
        else:
            raise ValueError("config must be yaml format.")


@tui(command="ui", help="Open the terminal UI")  # generate the terminal UI
@click.group()
def main():
    pass


@click.group()
def promptui():
    pass


main.add_command(promptui)


@click.group()
def modelcli():
    """Cross-model CLI commands (experimental)."""


main.add_command(modelcli)


@click.group()
def platform():
    """Install and validate platform bundles for Claude Code and Codex."""


main.add_command(platform)


@click.group()
def docqa():
    """Document QA CLI backed by the app's runtime/index/session data."""


main.add_command(docqa)


def _create_docqa_runtime():
    from ktem.docqa import DocQARuntime

    return DocQARuntime()


def _echo_json(payload):
    _echo_text(json.dumps(payload, ensure_ascii=False, indent=2))


def _echo_text(message=""):
    text = "" if message is None else str(message)
    try:
        click.echo(text)
    except UnicodeEncodeError:
        fallback = text.encode("ascii", errors="backslashreplace").decode("ascii")
        click.echo(fallback)


def _parse_graph_context_file(graph_context_file):
    if not graph_context_file:
        return {}

    with open(graph_context_file, encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise click.ClickException("--graph-context-file must contain a JSON object.")
    return payload


def _extract_json_payload(raw_output):
    lines = [line for line in str(raw_output or "").splitlines() if line.strip()]
    errors = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            continue
        payload = "\n".join(lines[index:])
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            errors.append(f"line {index + 1}: {exc}")
    raise click.ClickException(
        "Unable to parse JSON payload from acceptance output.\n"
        f"Errors: {errors}\n"
        f"Raw output:\n{raw_output}"
    )


def _repo_root():
    return Path(__file__).resolve().parents[3]


def _docqa_acceptance_script_path():
    return _repo_root() / "scripts" / "docqa_acceptance_matrix.py"


def _run_docqa_acceptance_matrix(*, keep_artifacts=False, verbose=False):
    script_path = _docqa_acceptance_script_path()
    if not script_path.exists():
        raise click.ClickException(
            f"Acceptance matrix script not found: {script_path}"
        )

    command = [sys.executable, str(script_path)]
    if keep_artifacts:
        command.append("--keep-artifacts")
    if verbose:
        command.append("--verbose")

    completed = subprocess.run(
        command,
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    try:
        payload = _extract_json_payload(completed.stdout)
    except click.ClickException:
        if completed.returncode != 0:
            raise click.ClickException(
                "DocQA acceptance matrix failed before emitting structured output.\n"
                f"STDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            ) from None
        raise

    if completed.returncode != 0 or payload.get("status") != "pass":
        details = [str(payload.get("error") or "DocQA acceptance matrix failed.")]
        if payload.get("work_dir"):
            details.append(f"Artifacts: {payload['work_dir']}")
        if payload.get("partial_results"):
            details.append(
                f"Completed checks: {len(payload.get('partial_results', []))}"
            )
        stderr_tail = str(payload.get("captured_stderr_tail") or "").strip()
        if stderr_tail:
            details.append(f"Captured stderr tail:\n{stderr_tail}")
        elif completed.stderr.strip():
            details.append(f"STDERR:\n{completed.stderr.strip()}")
        raise click.ClickException("\n".join(details))

    return payload


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


def _print_file_records(records, selected_ids=None):
    selected_ids = set(selected_ids or [])
    _echo_text("ID\tName\tTokens\tSize\tLoader")
    for record in records:
        marker = "*" if record.file_id in selected_ids else ""
        _echo_text(
            f"{record.file_id}{marker}\t{record.name}\t{record.tokens}\t{record.size}\t{record.loader}"
        )


def _print_session_summaries(summaries):
    _echo_text("ID\tName\tMessages\tFiles\tOrigin")
    for summary in summaries:
        _echo_text(
            f"{summary.conversation_id}\t{summary.name}\t{summary.message_count}\t{summary.graph_source_count}\t{summary.origin}"
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
            default=1,
            show_default=True,
            type=int,
            help="Active page number for page-level QA.",
        ),
        click.option(
            "--selected-text",
            default="",
            help="Explicit selected text to bias page-level QA.",
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
    return matches[0]


def _run_docqa_repl(
    runtime,
    conversation_id,
    file_refs=(),
    active_file_ref="",
    page=1,
    selected_text="",
    graph_context_file="",
    reasoning=None,
    llm=None,
    citation=None,
    language=None,
    mindmap=None,
    json_output=False,
):
    from ktem.docqa import DocQARequest

    session = runtime.load_session(conversation_id)
    if session is None:
        raise click.ClickException(f"Conversation '{conversation_id}' does not exist.")

    selected_file_ids_override = None
    if file_refs:
        selected_file_ids_override = [record.file_id for record in _resolve_cli_files(runtime, file_refs)]

    active_record = _resolve_cli_active_file(runtime, active_file_ref)
    active_file_id = active_record.file_id if active_record else ""
    active_file_name = active_record.name if active_record else ""
    current_page = max(1, int(page or 1))
    current_selected_text = selected_text or ""
    graph_context = _parse_graph_context_file(graph_context_file)

    _echo_text(f"Conversation: {conversation_id}")
    _echo_text(
        "Commands: /files, /use <file>, /page <n>, /selected-text <text>, /history, /help, /exit"
    )

    while True:
        try:
            prompt = click.prompt("docqa", prompt_suffix="> ", show_default=False, default="")
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
                "Commands: /files, /use <file>, /page <n>, /selected-text <text>, /history, /help, /exit"
            )
            continue
        if prompt == "/files":
            _print_file_records(runtime.list_files(), selected_ids=selected_file_ids_override or session.graph_source_ids)
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
            if not value.isdigit():
                _echo_text("Usage: /page <number>")
                continue
            current_page = max(1, int(value))
            _echo_text(f"Page set to {current_page}.")
            continue
        if prompt.startswith("/selected-text"):
            current_selected_text = prompt[len("/selected-text") :].strip()
            _echo_text("Selected text updated.")
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
            DocQARequest(
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
            _echo_json(response.as_dict())
        else:
            _echo_text("")
            _print_docqa_response(response)
            _echo_text("")


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
    """Check DocQA runtime/index/session prerequisites."""
    runtime = _create_docqa_runtime()
    result = runtime.doctor()

    if json_output:
        _echo_json(result.as_dict())
    else:
        click.echo(f"Status: {'OK' if result.ok else 'FAIL'}")
        click.echo(f"App: {result.app_name}")
        click.echo(f"Default user: {result.default_user_id}")
        click.echo(f"Index: {result.index_name or '(missing)'}")
        click.echo(f"Default LLM: {result.llm_default or '(missing)'}")
        click.echo(f"Default embedding: {result.embedding_default or '(missing)'}")
        click.echo(f"Indexed files: {result.file_count}")
        click.echo(f"Saved sessions: {result.session_count}")
        if result.graph_cache_dir:
            click.echo(f"Graph cache: {result.graph_cache_dir}")
        for issue in result.issues:
            click.echo(f"- {issue}")

    if not result.ok:
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
    """Run the end-to-end DocQA acceptance matrix as a one-command health check."""
    payload = _run_docqa_acceptance_matrix(
        keep_artifacts=keep_artifacts,
        verbose=verbose,
    )

    if json_output:
        _echo_json(payload)
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
    """Index one or more local paths or URLs into the default file collection."""
    runtime = _create_docqa_runtime()
    result = runtime.index_paths(list(paths), reindex=reindex)

    if json_output:
        _echo_json(result.as_dict())
    else:
        click.echo(f"Indexed successfully: {len(result.successes)}")
        for item in result.successes:
            click.echo(f"- {item.get('file_name') or item.get('file_path')}")
        if result.failures:
            click.echo(f"Failed: {len(result.failures)}")
            for item in result.failures:
                click.echo(
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
    """List indexed files in the default file collection."""
    runtime = _create_docqa_runtime()
    records = runtime.list_files()

    if json_output:
        _echo_json([record.as_dict() for record in records])
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
    """Delete one or more indexed files by id or name."""
    runtime = _create_docqa_runtime()
    deleted = runtime.delete_files(list(refs))

    if json_output:
        _echo_json([record.as_dict() for record in deleted])
        return

    click.echo(f"Deleted: {len(deleted)}")
    for record in deleted:
        click.echo(f"- {record.name} ({record.file_id})")


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
    """List saved DocQA conversations."""
    runtime = _create_docqa_runtime()
    summaries = runtime.list_sessions()

    if json_output:
        _echo_json([summary.as_dict() for summary in summaries])
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
    """Run one DocQA turn and persist it to a conversation."""
    from ktem.docqa import DocQARequest

    runtime = _create_docqa_runtime()
    selected_records = _resolve_cli_files(runtime, file_refs)
    active_record = _resolve_cli_active_file(runtime, active_file)

    response = runtime.run_turn(
        DocQARequest(
            prompt=prompt,
            conversation_id=conversation or "",
            selected_file_ids=[record.file_id for record in selected_records]
            if file_refs
            else None,
            active_file_id=active_record.file_id if active_record else "",
            active_file_name=active_record.name if active_record else "",
            page_number=max(1, int(page or 1)),
            selected_text=selected_text or "",
            graph_context=_parse_graph_context_file(graph_context_file),
            reasoning_type=reasoning,
            llm=llm,
            use_mindmap=mindmap,
            use_citation=citation,
            language=language,
        )
    )

    if json_output:
        _echo_json(response.as_dict())
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
    """Open an interactive DocQA REPL backed by saved conversation state."""
    runtime = _create_docqa_runtime()
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
    runtime = _create_docqa_runtime()
    _run_docqa_repl(
        runtime=runtime,
        conversation_id=conversation_id,
        json_output=json_output,
    )


@modelcli.command("init-config")
@click.option(
    "--output",
    default="modelcli.yml",
    show_default=True,
    help="Output config file path.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    show_default=True,
    help="Overwrite the config file if it already exists.",
)
def modelcli_init_config(output, force):
    """Generate default multi-provider config file."""
    from kotaemon.modelcli import write_default_config

    try:
        path = write_default_config(output_path=output, force=force)
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Config written to {path}")


@modelcli.command("providers")
@click.option(
    "--config",
    "config_path",
    default="modelcli.yml",
    show_default=True,
    help="Runtime config path.",
)
def modelcli_providers(config_path):
    """List provider availability from current environment."""
    from pathlib import Path

    from kotaemon.modelcli import build_registry, load_runtime_config

    try:
        cfg = load_runtime_config(config_path if Path(config_path).exists() else None)
        registry = build_registry()
        report = registry.availability(cfg)
    except Exception as exc:  # pragma: no cover - defensive CLI wrapper
        raise click.ClickException(str(exc)) from exc

    click.echo("Provider\tAvailable\tReason")
    for name in registry.names():
        available, reason = report[name]
        status = "yes" if available else "no"
        click.echo(f"{name}\t{status}\t{reason}")


@modelcli.command("run")
@click.option("--prompt", required=True, help="Prompt to send to the selected model.")
@click.option("--model", required=True, help="Model name or alias.")
@click.option("--provider", required=False, help="Provider name override.")
@click.option(
    "--system-prompt",
    required=False,
    default=None,
    help="Optional system prompt.",
)
@click.option(
    "--temperature",
    required=False,
    default=0.2,
    type=float,
    show_default=True,
)
@click.option("--max-tokens", required=False, type=int, default=None)
@click.option(
    "--config",
    "config_path",
    default="modelcli.yml",
    show_default=True,
    help="Runtime config path.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Resolve provider/model and print execution plan without calling APIs.",
)
def modelcli_run(
    prompt,
    model,
    provider,
    system_prompt,
    temperature,
    max_tokens,
    config_path,
    dry_run,
):
    """Run a single completion through provider router."""
    from pathlib import Path

    from kotaemon.modelcli import (
        ModelRequest,
        build_registry,
        load_runtime_config,
        resolve_provider_name,
        run_completion,
    )

    try:
        cfg = load_runtime_config(config_path if Path(config_path).exists() else None)
        registry = build_registry()
        request = ModelRequest(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if dry_run:
            resolved_model = cfg.resolve_model_alias(request.model)
            provider_name = resolve_provider_name(
                registry=registry,
                cfg=cfg,
                model=resolved_model,
                provider=provider,
            )
            click.echo("mode: dry-run")
            click.echo(f"provider: {provider_name}")
            click.echo(f"model: {resolved_model}")
            return

        response = run_completion(
            registry=registry,
            cfg=cfg,
            request=request,
            provider=provider,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(response.text)


@platform.command("list")
def platform_list():
    """List supported external AI coding platforms."""
    from kotaemon.platform_support import get_platform_spec, list_platform_names

    click.echo("Platform\tDefault target")
    for name in list_platform_names():
        spec = get_platform_spec(name)
        click.echo(f"{name}\t{spec.target_subdir}")


@platform.command("status")
@click.option(
    "--platform",
    "platform_name",
    type=click.Choice(PLATFORM_CHOICES),
    required=True,
    help="Platform to inspect.",
)
@click.option(
    "--target-dir",
    default=None,
    help="Override install target root (defaults to ~/.claude or ~/.codex).",
)
def platform_status_cmd(platform_name, target_dir):
    """Show installed component status for one platform."""
    from kotaemon.platform_support import platform_status

    status = platform_status(platform_name, target_dir=target_dir)
    click.echo(f"Platform: {status.platform}")
    click.echo(f"Target: {status.target_dir}")
    click.echo("Component\tPresent")
    for component, present in status.component_state.items():
        click.echo(f"{component}\t{'yes' if present else 'no'}")


@platform.command("install")
@click.option(
    "--platform",
    "platform_name",
    type=click.Choice(PLATFORM_CHOICES),
    required=True,
    help="Platform to install.",
)
@click.option(
    "--mode",
    type=click.Choice(["full", "minimal", "selective"]),
    default="full",
    show_default=True,
    help="Install mode.",
)
@click.option(
    "--item",
    "items",
    multiple=True,
    help="Component names for selective mode (repeat option).",
)
@click.option(
    "--target-dir",
    default=None,
    help="Override install target root (defaults to ~/.claude or ~/.codex).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Preview changes without writing files.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    show_default=True,
    help="Skip confirmation prompt.",
)
def platform_install(platform_name, mode, items, target_dir, dry_run, yes):
    """Install platform bundle assets into target directories."""
    from kotaemon.platform_support import install_platform

    if mode == "selective" and not items:
        raise click.UsageError("Selective mode requires at least one --item option.")

    if not yes:
        if not click.confirm(
            f"Install platform '{platform_name}' using mode '{mode}'?"
        ):
            raise click.Abort()

    try:
        result = install_platform(
            platform_name=platform_name,
            mode=mode,
            target_dir=target_dir,
            items=items,
            dry_run=dry_run,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Platform: {result.platform}")
    click.echo(f"Target: {result.target_dir}")
    click.echo(f"Mode: {result.mode}")
    click.echo(f"Dry run: {'yes' if result.dry_run else 'no'}")
    click.echo(f"Components: {', '.join(result.components)}")
    click.echo(f"Changed paths: {len(result.changed_paths)}")
    click.echo(f"Merged paths: {len(result.merged_paths)}")
    click.echo(f"Sidecar paths: {len(result.sidecar_paths)}")
    if result.backup_dir:
        click.echo(f"Backup dir: {result.backup_dir}")

    for path in result.changed_paths:
        click.echo(f"- {path}")


@platform.command("validate")
@click.option(
    "--platform",
    "platform_name",
    type=click.Choice(PLATFORM_CHOICES),
    required=False,
    help="Validate one platform only.",
)
@click.option(
    "--installed",
    is_flag=True,
    default=False,
    show_default=True,
    help="Validate installed target instead of source bundle.",
)
@click.option(
    "--target-dir",
    default=None,
    help="Override install target root for --installed validation.",
)
def platform_validate(platform_name, installed, target_dir):
    """Validate platform bundles or installed targets."""
    from kotaemon.platform_support import validate_bundle, validate_installed

    if installed:
        if not platform_name:
            raise click.UsageError("--platform is required when using --installed.")
        result = validate_installed(platform_name, target_dir=target_dir)
        click.echo(
            f"{result.platform}: {'PASS' if result.valid else 'FAIL'}"
        )
        for error in result.errors:
            click.echo(f"  - {error}")
        if not result.valid:
            raise click.ClickException("Installed validation failed.")
        return

    results = validate_bundle(platform_name=platform_name)
    all_valid = True
    for result in results:
        click.echo(f"{result.platform}: {'PASS' if result.valid else 'FAIL'}")
        for error in result.errors:
            click.echo(f"  - {error}")
        if not result.valid:
            all_valid = False

    if not all_valid:
        raise click.ClickException("Bundle validation failed.")


@promptui.command()
@click.argument("export_path", nargs=1)
@click.option("--output", default="promptui.yml", show_default=True, required=False)
def export(export_path, output):
    """Export a pipeline to a config file"""
    import sys

    from theflow.utils.modules import import_dotted_string

    from kotaemon.contribs.promptui.config import export_pipeline_to_config

    sys.path.append(os.getcwd())
    cls = import_dotted_string(export_path, safe=False)
    export_pipeline_to_config(cls, output)
    check_config_format(output)


@promptui.command()
@click.argument("run_path", required=False, default="promptui.yml")
@click.option(
    "--share",
    is_flag=True,
    show_default=True,
    default=False,
    help="Share the app through Gradio. Requires --username to enable authentication.",
)
@click.option(
    "--username",
    required=False,
    help=(
        "Username for the user. If not provided, the promptui will not have "
        "authentication."
    ),
)
@click.option(
    "--password",
    required=False,
    help="Password for the user. If not provided, will be prompted.",
)
@click.option(
    "--appname",
    required=False,
    help="The share app subdomain. Requires --share and --username",
)
@click.option(
    "--port",
    required=False,
    help="Port to run the app. If not provided, will $GRADIO_SERVER_PORT (7860)",
)
def run(run_path, share, username, password, appname, port):
    """Run the UI from a config file

    Examples:

        \b
        # Run with default config file
        $ kh promptui run

        \b
        # Run with username and password supplied
        $ kh promptui run --username admin --password password

        \b
        # Run with username and prompted password
        $ kh promptui run --username admin

        # Run and share to promptui
        # kh promptui run --username admin --password password --share --appname hey \
                --port 7861
    """
    import sys

    from kotaemon.contribs.promptui.ui import build_from_dict

    sys.path.append(os.getcwd())

    check_config_format(run_path)
    demo = build_from_dict(run_path)

    params: dict = {}
    if username is not None:
        if password is not None:
            auth = (username, password)
        else:
            auth = (username, click.prompt("Password", hide_input=True))
        params["auth"] = auth

    port = int(port) if port else int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    params["server_port"] = port

    if share:
        if username is None:
            raise ValueError(
                "Username must be provided to enable authentication for sharing"
            )
        if appname:
            from kotaemon.contribs.promptui.tunnel import Tunnel

            tunnel = Tunnel(
                appname=str(appname), username=str(username), local_port=port
            )
            url = tunnel.run()
            print(f"App is shared at {url}")
        else:
            params["share"] = True
            print("App is shared at Gradio")

    demo.launch(**params)


@main.command()
@click.argument("module", required=True)
@click.option(
    "--output", default="docs.md", required=False, help="The output markdown file"
)
@click.option(
    "--separation-level", required=False, default=1, help="Organize markdown layout"
)
def makedoc(module, output, separation_level):
    """Make documentation for module `module`

    Example:

        \b
        # Make component documentation for kotaemon library
        $ kh makedoc kotaemon
    """
    from kotaemon.contribs.docs import make_doc

    make_doc(module, output, separation_level)
    print(f"Documentation exported to {output}")


@main.command()
@click.option(
    "--template",
    default="project-default",
    required=False,
    help="Template name",
    show_default=True,
)
def start_project(template):
    """Start a project from a template.

    Important: the value for --template corresponds to the name of the template folder,
    which is located at https://github.com/Cinnamon/kotaemon/tree/main/templates
    The default value is "project-default", which should work when you are starting a
    client project.
    """

    print("Retrieving template...")
    os.system(
        "cookiecutter git@github.com:Cinnamon/kotaemon.git "
        f"--directory='templates/{template}'"
    )


if __name__ == "__main__":
    main()
