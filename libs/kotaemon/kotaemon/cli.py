import os

import click
import yaml
from trogon import tui


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
