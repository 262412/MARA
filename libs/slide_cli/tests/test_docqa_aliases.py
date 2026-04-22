from click.testing import CliRunner

from slide_cli.cli import main
from slide_cli.docqa_cli import docqa as local_docqa_group


def test_docqa_aliases_point_to_canonical_commands():
    docqa_group = main.commands["docqa"]
    assert docqa_group is local_docqa_group
    expected_targets = {
        "ask": "ask",
        "index": "index",
        "files": "files",
        "docqa-sessions": "sessions",
        "resume-docqa": "resume",
    }

    for alias_name, target_name in expected_targets.items():
        alias_command = main.commands[alias_name]
        target_command = docqa_group.commands[target_name]

        assert alias_command.callback is target_command.callback
        assert [param.name for param in alias_command.params] == [
            param.name for param in target_command.params
        ]
        assert alias_command.help == target_command.help

    assert main.commands["resume"] is not docqa_group.commands["resume"]
    assert "sessions" in main.commands
    assert main.commands["sessions"] is not docqa_group.commands["sessions"]


def test_docqa_alias_help_is_available():
    runner = CliRunner()

    result = runner.invoke(main, ["docqa-sessions", "--help"])

    assert result.exit_code == 0, result.output
    assert "docqa-sessions" in result.output
