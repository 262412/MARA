from __future__ import annotations

import json
from pathlib import Path

import click


def _echo_json(payload):
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _echo_text(message=""):
    text = "" if message is None else str(message)
    try:
        click.echo(text)
    except UnicodeEncodeError:
        click.echo(text.encode("ascii", errors="backslashreplace").decode("ascii"))


def _collect_doctor_payload():
    from .runtime import collect_doctor_payload

    return collect_doctor_payload()


def _resolve_workspace_path(
    candidate: str,
    *,
    cwd: str | None = None,
    allow_missing: bool = False,
):
    from .runtime import resolve_workspace_path as _resolve_workspace_path_impl

    return _resolve_workspace_path_impl(candidate, cwd=cwd, allow_missing=allow_missing)


def list_workspace_files(*, cwd: str | None = None):
    from .runtime import list_workspace_files as _list_workspace_files

    return _list_workspace_files(cwd=cwd)


def read_workspace_file(path: str, *, cwd: str | None = None):
    from .runtime import read_workspace_file as _read_workspace_file

    return _read_workspace_file(path, cwd=cwd)


def write_workspace_file(
    *,
    path: str,
    content: str,
    cwd: str | None = None,
    append: bool = False,
):
    from .runtime import write_workspace_file as _write_workspace_file

    return _write_workspace_file(path=path, content=content, cwd=cwd, append=append)


def delete_workspace_path(
    path: str,
    *,
    cwd: str | None = None,
    recursive: bool = False,
    yes: bool = False,
):
    from .runtime import delete_workspace_path as _delete_workspace_path

    return _delete_workspace_path(
        path,
        cwd=cwd,
        recursive=recursive,
        yes=yes,
    )


def run_workspace_shell(
    *,
    command: str,
    cwd: str | None = None,
    shell_timeout_sec: int = 15,
):
    from .runtime import run_workspace_shell as _run_workspace_shell

    return _run_workspace_shell(
        command=command,
        cwd=cwd,
        shell_timeout_sec=shell_timeout_sec,
    )


def export_deck_pdf(source_path: str, *, output_path: str | None = None):
    from .deck import export_deck_pdf as _export_deck_pdf

    return _export_deck_pdf(source_path, output_path=output_path)


def inspect_slide_deck(input_path: str):
    from .runtime import inspect_slide_deck as _inspect_slide_deck

    return _inspect_slide_deck(input_path)


def read_slide_summary(input_path: str, *, slide_number: int):
    from .runtime import read_slide_summary as _read_slide_summary

    return _read_slide_summary(input_path, slide_number=slide_number)


def extract_slide_text(input_path: str, *, slide_number: int | None = None):
    from .runtime import extract_slide_text as _extract_slide_text

    return _extract_slide_text(input_path, slide_number=slide_number)


def search_slide_deck(input_path: str, *, query: str):
    from .runtime import search_slide_deck as _search_slide_deck

    return _search_slide_deck(input_path, query=query)


def review_slide_deck(input_path: str):
    from .runtime import review_slide_deck as _review_slide_deck

    return _review_slide_deck(input_path)


def run_slide_task(**kwargs):
    from .runtime import run_slide_task as _run_slide_task

    return _run_slide_task(**kwargs)


def apply_session_patch(session_id, *, output_path=None, base_dir=None):
    from .runtime import apply_session_patch as _apply_session_patch

    return _apply_session_patch(
        session_id,
        output_path=output_path,
        base_dir=base_dir,
    )


def _slide_session_store_cls():
    from .session_store import SlideSessionStore

    return SlideSessionStore


def _load_docqa_group() -> click.Group:
    from .docqa_cli import docqa

    return docqa


def _load_kotaemon_group(group_name: str) -> click.Group:
    from kotaemon import cli as kotaemon_cli

    return getattr(kotaemon_cli, group_name)


class _LazyDocQAGroup(click.Group):
    def __init__(self) -> None:
        super().__init__(
            name="docqa",
            help="Document QA CLI backed by the app's runtime/index/session data.",
            short_help="Document QA CLI backed by the app's runtime/index/session data.",
        )

    def _group(self) -> click.Group:
        return _load_docqa_group()

    def list_commands(self, ctx):
        return self._group().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        return self._group().get_command(ctx, cmd_name)

    def get_help(self, ctx):
        return self._group().get_help(ctx)

    def invoke(self, ctx):
        return self._group().invoke(ctx)


class _LazyKotaemonGroup(click.Group):
    def __init__(self, *, name: str, source_group: str, help_text: str) -> None:
        self.source_group = source_group
        super().__init__(name=name, help=help_text, short_help=help_text)

    def _group(self) -> click.Group:
        return _load_kotaemon_group(self.source_group)

    def list_commands(self, ctx):
        return self._group().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        return self._group().get_command(ctx, cmd_name)


@click.group()
def main():
    """Unified slide product CLI.

    Top-level agent line:
    - `slide doctor` validates the agent runtime and provider setup.
    - `slide inspect`, `slide read-slide`, `slide extract`, and
      `slide search` expose read-only deck observability commands.
    - `slide files`, `slide read`, `slide write`, `slide delete`, and
      `slide shell` expose explicit high-permission workspace operations.
    - `slide apply`, `slide export-pdf`, and `slide review` expose
      deterministic deck-output and inspection workflows.
    - `slide run` executes one high-permission deck workflow.
    - `slide chat`, `slide sessions`, and `slide resume` manage interactive
      deck-agent sessions.

    Specialist DocQA line:
    - `slide docqa ...` owns the document QA workflow and focused DocQA skills.

    Support lines:
    - `slide app ...` owns packaged app setup, doctor, and launch workflows.
    - `slide model ...` owns shared model routing workflows.
    - `slide platform ...` owns Codex and Claude Code support asset workflows.
    """


main.add_command(_LazyDocQAGroup(), "docqa")
main.add_command(
    _LazyKotaemonGroup(
        name="app",
        source_group="app",
        help_text="Packaged app setup, doctor, and launch workflows.",
    ),
    "app",
)
main.add_command(
    _LazyKotaemonGroup(
        name="model",
        source_group="modelcli",
        help_text="Shared model routing workflows.",
    ),
    "model",
)
main.add_command(
    _LazyKotaemonGroup(
        name="platform",
        source_group="platform",
        help_text="Install and validate Codex and Claude Code support assets.",
    ),
    "platform",
)


@main.command("doctor")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def doctor(json_output):
    """Validate the top-level slide agent runtime and provider setup."""
    payload = _collect_doctor_payload()
    if json_output:
        _echo_json(payload)
        return

    _echo_text(f"Status: {'OK' if payload.get('ok') else 'FAIL'}")
    _echo_text(f"Config: {payload.get('config_path') or '(default)'}")
    _echo_text(f"python-pptx: {'yes' if payload.get('python_pptx') else 'no'}")
    _echo_text(f"LibreOffice: {'yes' if payload.get('libreoffice') else 'no'}")
    _echo_text("Providers:")
    for name, info in payload.get("providers", {}).items():
        status = "yes" if info.get("available") else "no"
        _echo_text(f"- {name}: {status} ({info.get('reason')})")


@main.command("files")
@click.option("--cwd", default=None, help="Workspace root to inspect.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def files_cmd(cwd, json_output):
    """List workspace files available to the top-level agent line."""
    payload = list_workspace_files(cwd=cwd)
    if json_output:
        _echo_json(payload)
        return

    for path in payload["paths"]:
        _echo_text(path)


@main.command("read")
@click.argument("path", required=True)
@click.option("--cwd", default=None, help="Workspace root to inspect.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def read_cmd(path, cwd, json_output):
    """Read one workspace text file from the top-level agent line."""
    try:
        payload = read_workspace_file(path, cwd=cwd)
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(payload["content"])


@main.command("write")
@click.argument("path", required=True)
@click.option("--content", required=True, help="UTF-8 text content to write.")
@click.option(
    "--append",
    is_flag=True,
    default=False,
    show_default=True,
    help="Append instead of overwrite.",
)
@click.option("--cwd", default=None, help="Workspace root to inspect.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def write_cmd(path, content, append, cwd, json_output):
    """Write or append one workspace text file from the top-level agent line."""
    try:
        payload = write_workspace_file(
            path=path, content=content, cwd=cwd, append=append
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(
        f"Wrote {payload['chars_written']} characters to {payload['path']}"
        + (" (append)" if payload["append"] else "")
    )


@main.command("delete")
@click.argument("path", required=True)
@click.option(
    "--recursive",
    is_flag=True,
    default=False,
    show_default=True,
    help="Allow recursive directory deletion inside the workspace root.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    show_default=True,
    help="Skip the interactive confirmation prompt.",
)
@click.option("--cwd", default=None, help="Workspace root to inspect.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def delete_cmd(path, recursive, yes, cwd, json_output):
    """Delete one workspace file or directory from the top-level agent line."""
    try:
        _workspace_root, resolved = _resolve_workspace_path(path, cwd=cwd)
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if not yes:
        target_kind = "directory" if resolved.is_dir() else "file"
        prompt = (
            f"Delete {target_kind} '{resolved}'"
            + (" recursively" if resolved.is_dir() else "")
            + "?"
        )
        click.confirm(prompt, default=False, abort=True)

    try:
        payload = delete_workspace_path(
            path,
            cwd=cwd,
            recursive=recursive,
            yes=yes,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(f"Deleted {payload['deleted_type']} {payload['path']}")


@main.command("shell")
@click.option("--command", required=True, help="Shell command to execute.")
@click.option("--cwd", default=None, help="Workspace root to inspect.")
@click.option(
    "--shell-timeout",
    "shell_timeout_sec",
    default=15,
    show_default=True,
    type=int,
    help="Shell command timeout in seconds.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def shell_cmd(command, cwd, shell_timeout_sec, json_output):
    """Run one workspace shell command from the top-level agent line."""
    try:
        payload = run_workspace_shell(
            command=command,
            cwd=cwd,
            shell_timeout_sec=shell_timeout_sec,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(f"returncode: {payload['returncode']}")
    _echo_text(f"stdout:\n{payload['stdout'] or '(empty)'}")
    _echo_text(f"stderr:\n{payload['stderr'] or '(empty)'}")


@main.command("inspect")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def inspect_cmd(input_path, json_output):
    """Inspect one slide deck from the top-level agent line."""
    try:
        payload = inspect_slide_deck(str(input_path))
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(payload["summary"])


@main.command("read-slide")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option(
    "--slide", "slide_number", required=True, type=int, help="Slide number to read."
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def read_slide_cmd(input_path, slide_number, json_output):
    """Read one slide summary from the top-level agent line."""
    try:
        payload = read_slide_summary(str(input_path), slide_number=slide_number)
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(payload["summary"])


@main.command("extract")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option(
    "--slide",
    "slide_number",
    default=None,
    type=int,
    help="Optional slide number to extract instead of the whole deck.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def extract_cmd(input_path, slide_number, json_output):
    """Extract plain text from one slide deck or one slide."""
    try:
        payload = extract_slide_text(str(input_path), slide_number=slide_number)
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(payload["text"])


@main.command("search")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option("--query", required=True, help="Case-insensitive search string.")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def search_cmd(input_path, query, json_output):
    """Search one slide deck summary from the top-level agent line."""
    try:
        payload = search_slide_deck(str(input_path), query=query)
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    if payload["matches"]:
        for match in payload["matches"]:
            _echo_text(match)
        return

    _echo_text("No matches found.")


@main.command("apply")
@click.argument("session_id", required=True, metavar="session_id")
@click.option(
    "--output",
    default=None,
    type=click.Path(dir_okay=False),
    help="Optional output deck path for the applied patch.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def apply_cmd(session_id, output, json_output):
    """Apply the latest saved patch from a top-level slide session."""
    try:
        payload = apply_session_patch(
            session_id,
            output_path=str(output) if output else None,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(f"Session: {payload['session_id']}")
    _echo_text(f"Output: {payload['output_path']}")
    _echo_text(f"Applied edits: {payload.get('applied_count', 0)}")


@main.command("export-pdf")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option(
    "--output",
    default=None,
    type=click.Path(dir_okay=False),
    help="Optional output PDF path.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def export_pdf_cmd(input_path, output, json_output):
    """Export one slide deck to PDF from the top-level agent line."""
    try:
        output_path = export_deck_pdf(
            str(input_path),
            output_path=str(output) if output else None,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    payload = {
        "input_path": str(input_path),
        "output_path": str(output_path),
    }
    if json_output:
        _echo_json(payload)
        return

    _echo_text(f"Output: {payload['output_path']}")


@main.command("review")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def review_cmd(input_path, json_output):
    """Review one slide deck with deterministic top-level heuristics."""
    try:
        payload = review_slide_deck(str(input_path))
    except Exception as exc:
        raise click.ClickException(str(exc)) from None

    if json_output:
        _echo_json(payload)
        return

    _echo_text(json.dumps(payload, ensure_ascii=False, indent=2))


@main.command("run")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option("--prompt", required=True, help="Instruction for the slide agent.")
@click.option(
    "--output",
    default=None,
    type=click.Path(dir_okay=False),
    help="Optional output file path for an applied rewrite.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    show_default=True,
    help="Apply the generated patch to a deck copy. Without this flag, run stays in preview mode unless --output is provided.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Generate a response and patch preview without writing a new deck.",
)
@click.option("--model", default="gpt-4o-mini", show_default=True)
@click.option("--provider", default=None, help="Optional provider override.")
@click.option(
    "--config",
    "config_path",
    default="modelcli.yml",
    show_default=True,
    help="Runtime config path.",
)
@click.option("--cwd", default=None, help="Working directory for session context.")
@click.option(
    "--approval-policy",
    type=click.Choice(["auto", "confirm"]),
    default="confirm",
    show_default=True,
    help="Approval policy for operations that may write artifacts.",
)
@click.option(
    "--shell-timeout",
    "shell_timeout_sec",
    default=15,
    show_default=True,
    type=int,
    help="Shell command timeout in seconds.",
)
@click.option(
    "--max-iterations",
    default=4,
    show_default=True,
    type=int,
    help="Maximum number of agent reasoning steps.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def run_cmd(
    input_path,
    prompt,
    output,
    apply,
    dry_run,
    model,
    provider,
    config_path,
    cwd,
    approval_policy,
    shell_timeout_sec,
    max_iterations,
    json_output,
):
    """Run one high-permission slide agent workflow."""
    if apply and dry_run:
        raise click.ClickException("--apply and --dry-run cannot be used together.")

    apply_mode = "apply" if apply or output else "preview"
    result = run_slide_task(
        input_path=str(input_path),
        prompt=prompt,
        output_path=str(output) if output else None,
        dry_run=dry_run,
        model=model,
        provider=provider,
        config_path=config_path,
        cwd=cwd,
        apply_mode=apply_mode,
        approval_policy=approval_policy,
        shell_timeout_sec=shell_timeout_sec,
        max_iterations=max_iterations,
    )
    if json_output:
        _echo_json(result)
        return

    _echo_text(f"Session: {result['session_id']}")
    _echo_text(result["response"])
    if result.get("patch"):
        _echo_text("")
        _echo_text(f"Patch summary: {result['patch'].get('summary', '')}")
    if result.get("output_path"):
        _echo_text(f"Output: {result['output_path']}")
    elif result.get("suggested_output_path"):
        _echo_text(
            f"Preview only. Use --apply or --output to write: {result['suggested_output_path']}"
        )


@main.command("sessions")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output.",
)
def sessions_cmd(json_output):
    """Inspect saved top-level slide agent sessions."""
    store = _slide_session_store_cls()()
    sessions = store.list_sessions()
    payload = [session.as_dict() for session in sessions]
    if json_output:
        _echo_json(payload)
        return

    _echo_text("ID\tMode\tTitle\tUpdated")
    for session in sessions:
        _echo_text(
            f"{session.session_id}\t{session.mode}\t{session.title}\t{session.updated_at}"
        )


def _run_repl(
    *,
    session_id: str,
    input_path: str,
    model: str,
    provider: str | None,
    config_path: str,
    cwd: str | None,
    approval_policy: str,
    shell_timeout_sec: int,
    max_iterations: int,
    json_output: bool,
):
    _echo_text(f"Session: {session_id}")
    _echo_text("Commands: /exit, /history, /apply [output-path]")

    store = _slide_session_store_cls()()
    while True:
        try:
            user_prompt = click.prompt(
                "slide", prompt_suffix="> ", show_default=False, default=""
            )
        except (EOFError, click.Abort):
            _echo_text("")
            break

        user_prompt = str(user_prompt or "").strip()
        if not user_prompt:
            continue
        if user_prompt == "/exit":
            break
        if user_prompt.startswith("/apply"):
            output_path = user_prompt[len("/apply") :].strip() or None
            try:
                applied = apply_session_patch(session_id, output_path=output_path)
            except Exception as exc:
                _echo_text(f"Apply failed: {exc}")
            else:
                _echo_text(f"Output: {applied['output_path']}")
            continue
        if user_prompt == "/history":
            session = store.load_session(session_id)
            if session is None or not session.events:
                _echo_text("No history yet.")
                continue
            for event in session.events:
                role = str(event.get("role", "unknown")).upper()
                content = str(event.get("content", ""))
                _echo_text(f"[{role}] {content}")
            continue

        result = run_slide_task(
            input_path=input_path,
            prompt=user_prompt,
            dry_run=True,
            model=model,
            provider=provider,
            config_path=config_path,
            cwd=cwd,
            session_id=session_id,
            apply_mode="confirm",
            approval_policy=approval_policy,
            shell_timeout_sec=shell_timeout_sec,
            max_iterations=max_iterations,
        )
        if json_output:
            _echo_json(result)
        else:
            _echo_text(result["response"])
            if result.get("can_apply"):
                output_hint = (
                    result.get("suggested_output_path") or "(default output path)"
                )
                if click.confirm(
                    f"Apply this patch to a deck copy now? [{output_hint}]",
                    default=False,
                ):
                    try:
                        applied = apply_session_patch(session_id)
                    except Exception as exc:
                        _echo_text(f"Apply failed: {exc}")
                    else:
                        _echo_text(f"Output: {applied['output_path']}")


@main.command("chat")
@click.option("--file", "input_path", required=True, type=click.Path(exists=True))
@click.option("--prompt", default="", help="Optional first prompt to run before REPL.")
@click.option("--model", default="gpt-4o-mini", show_default=True)
@click.option("--provider", default=None, help="Optional provider override.")
@click.option(
    "--config",
    "config_path",
    default="modelcli.yml",
    show_default=True,
    help="Runtime config path.",
)
@click.option("--cwd", default=None, help="Working directory for session context.")
@click.option(
    "--approval-policy",
    type=click.Choice(["auto", "confirm"]),
    default="confirm",
    show_default=True,
    help="Approval policy for operations that may write artifacts.",
)
@click.option(
    "--shell-timeout",
    "shell_timeout_sec",
    default=15,
    show_default=True,
    type=int,
    help="Shell command timeout in seconds.",
)
@click.option(
    "--max-iterations",
    default=4,
    show_default=True,
    type=int,
    help="Maximum number of agent reasoning steps.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output for each answer.",
)
def chat_cmd(
    input_path,
    prompt,
    model,
    provider,
    config_path,
    cwd,
    approval_policy,
    shell_timeout_sec,
    max_iterations,
    json_output,
):
    """Open an interactive high-permission slide agent session."""
    store = _slide_session_store_cls()()
    session = store.create_session(
        mode="chat",
        title=f"Chat: {Path(input_path).name}",
        input_path=str(input_path),
        prompt=prompt or "",
        cwd=cwd or "",
    )

    if prompt:
        result = run_slide_task(
            input_path=str(input_path),
            prompt=prompt,
            dry_run=True,
            model=model,
            provider=provider,
            config_path=config_path,
            cwd=cwd,
            session_id=session.session_id,
            apply_mode="confirm",
            approval_policy=approval_policy,
            shell_timeout_sec=shell_timeout_sec,
            max_iterations=max_iterations,
        )
        if json_output:
            _echo_json(result)
        else:
            _echo_text(result["response"])

    _run_repl(
        session_id=session.session_id,
        input_path=str(input_path),
        model=model,
        provider=provider,
        config_path=config_path,
        cwd=cwd,
        approval_policy=approval_policy,
        shell_timeout_sec=shell_timeout_sec,
        max_iterations=max_iterations,
        json_output=json_output,
    )


@main.command("resume")
@click.argument("session_id", required=True)
@click.option("--model", default="gpt-4o-mini", show_default=True)
@click.option("--provider", default=None, help="Optional provider override.")
@click.option(
    "--config",
    "config_path",
    default="modelcli.yml",
    show_default=True,
    help="Runtime config path.",
)
@click.option(
    "--approval-policy",
    type=click.Choice(["auto", "confirm"]),
    default="confirm",
    show_default=True,
    help="Approval policy for operations that may write artifacts.",
)
@click.option(
    "--shell-timeout",
    "shell_timeout_sec",
    default=15,
    show_default=True,
    type=int,
    help="Shell command timeout in seconds.",
)
@click.option(
    "--max-iterations",
    default=4,
    show_default=True,
    type=int,
    help="Maximum number of agent reasoning steps.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    show_default=True,
    help="Emit structured JSON output for each answer.",
)
def resume_cmd(
    session_id,
    model,
    provider,
    config_path,
    approval_policy,
    shell_timeout_sec,
    max_iterations,
    json_output,
):
    """Resume a saved top-level slide agent session."""
    store = _slide_session_store_cls()()
    session = store.load_session(session_id)
    if session is None:
        raise click.ClickException(f"Session '{session_id}' does not exist.")
    _run_repl(
        session_id=session_id,
        input_path=session.input_path,
        model=model,
        provider=provider,
        config_path=config_path,
        cwd=session.cwd,
        approval_policy=approval_policy,
        shell_timeout_sec=shell_timeout_sec,
        max_iterations=max_iterations,
        json_output=json_output,
    )


if __name__ == "__main__":
    main()
