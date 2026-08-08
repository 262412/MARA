import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from slide_cli.docqa_cli import docqa as compat_docqa

from kotaemon.cli import main as mara_cli


class _Runtime:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[list[str], bool]] = []
        self.fail = fail

    def index_paths(self, paths, reindex=False):
        self.calls.append((paths, reindex))
        failures = (
            [
                {
                    "file_name": "broken.pdf",
                    "status": "failed",
                    "message": "unsupported content",
                }
            ]
            if self.fail
            else []
        )
        return SimpleNamespace(
            successes=[{"file_name": "paper.pdf", "status": "success"}],
            failures=failures,
            as_dict=lambda: {
                "successes": [{"file_name": "paper.pdf", "status": "success"}],
                "failures": failures,
                "debug_messages": [],
            },
        )


@pytest.mark.parametrize(
    ("command", "patch_target"),
    [
        (mara_cli, "kotaemon.cli._create_docqa_runtime"),
        (compat_docqa, "slide_cli.docqa_cli.create_docqa_runtime"),
    ],
)
def test_index_json_preserves_paths_reindex_and_result_shape(
    monkeypatch, command, patch_target
):
    runtime = _Runtime()
    monkeypatch.setattr(patch_target, lambda: runtime)
    args = (
        ["docqa", "index", "paper.pdf", "--reindex", "--json"]
        if command is mara_cli
        else ["index", "paper.pdf", "--reindex", "--json"]
    )

    result = CliRunner().invoke(command, args)

    assert result.exit_code == 0, result.output
    assert runtime.calls == [(["paper.pdf"], True)]
    assert json.loads(result.output) == {
        "successes": [{"file_name": "paper.pdf", "status": "success"}],
        "failures": [],
        "debug_messages": [],
    }


@pytest.mark.parametrize(
    ("command", "patch_target"),
    [
        (mara_cli, "kotaemon.cli._create_docqa_runtime"),
        (compat_docqa, "slide_cli.docqa_cli.create_docqa_runtime"),
    ],
)
def test_index_partial_failure_remains_nonzero(monkeypatch, command, patch_target):
    runtime = _Runtime(fail=True)
    monkeypatch.setattr(patch_target, lambda: runtime)
    args = (
        ["docqa", "index", "paper.pdf", "broken.pdf"]
        if command is mara_cli
        else ["index", "paper.pdf", "broken.pdf"]
    )

    result = CliRunner().invoke(command, args)

    assert result.exit_code != 0
    assert "Some inputs failed to index" in result.output
