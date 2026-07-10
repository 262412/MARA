import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from ktem.index.file.deletion import DeletionError
from slide_cli.docqa_cli import docqa as compat_docqa

from kotaemon.cli import main as mara_cli


class _FailingRuntime:
    def delete_files(self, _refs):
        raise DeletionError(
            stage="docstore", file_id="file-9", reason="service unavailable"
        )


class _SuccessfulRuntime:
    def delete_files(self, _refs):
        return [
            SimpleNamespace(
                file_id="file-1",
                name="report.pdf",
                as_dict=lambda: {
                    "file_id": "file-1",
                    "name": "report.pdf",
                    "tokens": 7,
                    "size": 42,
                    "loader": "PDFReader",
                },
            )
        ]


@pytest.mark.parametrize(
    ("command", "patch_target"),
    [
        (mara_cli, "kotaemon.cli._create_docqa_runtime"),
        (compat_docqa, "slide_cli.docqa_cli.create_docqa_runtime"),
    ],
)
def test_delete_failure_is_nonzero_and_actionable(monkeypatch, command, patch_target):
    monkeypatch.setattr(patch_target, lambda: _FailingRuntime())
    args = (
        ["docqa", "delete", "file-9"] if command is mara_cli else ["delete", "file-9"]
    )

    result = CliRunner().invoke(command, args)

    assert result.exit_code != 0
    assert "stage=docstore" in result.output
    assert "file_id=file-9" in result.output


@pytest.mark.parametrize(
    ("command", "patch_target"),
    [
        (mara_cli, "kotaemon.cli._create_docqa_runtime"),
        (compat_docqa, "slide_cli.docqa_cli.create_docqa_runtime"),
    ],
)
def test_delete_success_json_shape_is_unchanged(monkeypatch, command, patch_target):
    monkeypatch.setattr(patch_target, lambda: _SuccessfulRuntime())
    args = (
        ["docqa", "delete", "file-1", "--json"]
        if command is mara_cli
        else ["delete", "file-1", "--json"]
    )

    result = CliRunner().invoke(command, args)

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [
        {
            "file_id": "file-1",
            "name": "report.pdf",
            "tokens": 7,
            "size": 42,
            "loader": "PDFReader",
        }
    ]
