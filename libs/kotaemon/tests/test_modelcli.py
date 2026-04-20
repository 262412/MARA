import yaml
from click.testing import CliRunner

from kotaemon.cli import main


def test_modelcli_init_config(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "modelcli.yml"

    result = runner.invoke(
        main, ["modelcli", "init-config", "--output", str(config_path)]
    )

    assert result.exit_code == 0, result.output
    assert config_path.exists()

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert content["default_provider"] == "openai"
    assert "openrouter" in content["providers"]


def test_modelcli_providers_with_default_config_when_file_missing():
    runner = CliRunner()
    result = runner.invoke(main, ["modelcli", "providers", "--config", "not-found.yml"])

    assert result.exit_code == 0, result.output
    assert "Provider\tAvailable\tReason" in result.output
    assert "openai" in result.output
    assert "anthropic" in result.output


def test_modelcli_run_dry_run_resolves_provider(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "modelcli.yml"

    init_result = runner.invoke(
        main,
        ["modelcli", "init-config", "--output", str(config_path)],
    )
    assert init_result.exit_code == 0, init_result.output

    run_result = runner.invoke(
        main,
        [
            "modelcli",
            "run",
            "--prompt",
            "hello",
            "--model",
            "gpt-4o-mini",
            "--config",
            str(config_path),
            "--dry-run",
        ],
    )

    assert run_result.exit_code == 0, run_result.output
    assert "mode: dry-run" in run_result.output
    assert "provider: openai" in run_result.output
    assert "model: gpt-4o-mini" in run_result.output
