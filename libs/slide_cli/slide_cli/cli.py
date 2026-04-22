from __future__ import annotations

import json
from copy import copy
from pathlib import Path

import click

from .docqa_cli import docqa as docqa_group

from .runtime import apply_session_patch, collect_doctor_payload, run_slide_task
from .session_store import SlideSessionStore


def _echo_json(payload):
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _echo_text(message=""):
    text = "" if message is None else str(message)
    try:
        click.echo(text)
    except UnicodeEncodeError:
        click.echo(text.encode("ascii", errors="backslashreplace").decode("ascii"))


def _collect_doctor_payload():
    return collect_doctor_payload()


def _get_docqa_command(command_name: str) -> click.Command:
    command = docqa_group.get_command(None, command_name)
    if command is None:
        raise RuntimeError(f"DocQA command '{command_name}' is unavailable.")
    return command


def _clone_docqa_command(command_name: str) -> click.Command:
    command = _get_docqa_command(command_name)
    return click.Command(
        name=command.name,
        callback=command.callback,
        params=[copy(param) for param in command.params],
        help=command.help,
        short_help=command.short_help,
        context_settings=getattr(command, "context_settings", None),
        epilog=getattr(command, "epilog", None),
        add_help_option=getattr(command, "add_help_option", True),
        no_args_is_help=getattr(command, "no_args_is_help", False),
        hidden=getattr(command, "hidden", False),
    )


DOCQA_TOP_LEVEL_ALIASES = {
    "ask": "ask",
    "index": "index",
    "files": "files",
    "docqa-sessions": "sessions",
    "resume-docqa": "resume",
}


@click.group()
def main():
    """Agent CLI for reviewing and rewriting slide decks."""


main.add_command(docqa_group, "docqa")

for alias_name, command_name in DOCQA_TOP_LEVEL_ALIASES.items():
    main.add_command(_clone_docqa_command(command_name), alias_name)


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
        _echo_text(f"Preview only. Use --apply or --output to write: {result['suggested_output_path']}")


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
    store = SlideSessionStore()
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

    store = SlideSessionStore()
    while True:
        try:
            user_prompt = click.prompt("slide", prompt_suffix="> ", show_default=False, default="")
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
                output_hint = result.get("suggested_output_path") or "(default output path)"
                if click.confirm(f"Apply this patch to a deck copy now? [{output_hint}]", default=False):
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
    store = SlideSessionStore()
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
    store = SlideSessionStore()
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
