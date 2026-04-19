import os

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
