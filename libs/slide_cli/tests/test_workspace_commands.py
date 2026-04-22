from __future__ import annotations

from pathlib import Path
import sys

import pytest

from slide_cli import runtime


def test_workspace_file_helpers_round_trip(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    write_payload = runtime.write_workspace_file(
        path="notes.txt",
        content="hello from slide",
        cwd=str(workspace),
    )
    list_payload = runtime.list_workspace_files(cwd=str(workspace))
    read_payload = runtime.read_workspace_file("notes.txt", cwd=str(workspace))

    assert write_payload["path"] == "notes.txt"
    assert write_payload["chars_written"] == len("hello from slide")
    assert "notes.txt" in list_payload["paths"]
    assert read_payload["content"] == "hello from slide"


def test_workspace_file_helpers_block_paths_outside_root(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError):
        runtime.read_workspace_file(str(outside), cwd=str(workspace))

    with pytest.raises(ValueError):
        runtime.write_workspace_file(
            path=str(outside),
            content="nope",
            cwd=str(workspace),
        )

    with pytest.raises(ValueError):
        runtime.delete_workspace_path(str(outside), cwd=str(workspace), yes=True)


def test_delete_workspace_path_requires_recursive_for_directories(tmp_path):
    workspace = tmp_path / "workspace"
    target_dir = workspace / "nested"
    target_dir.mkdir(parents=True)
    (target_dir / "notes.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        runtime.delete_workspace_path("nested", cwd=str(workspace), yes=True)

    payload = runtime.delete_workspace_path(
        "nested",
        cwd=str(workspace),
        recursive=True,
        yes=True,
    )

    assert payload["path"] == "nested"
    assert payload["deleted_type"] == "directory"
    assert not target_dir.exists()


def test_run_workspace_shell_returns_structured_payload(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    payload = runtime.run_workspace_shell(
        command=f'"{sys.executable}" -c "print(123)"',
        cwd=str(workspace),
        shell_timeout_sec=5,
    )

    assert payload["returncode"] == 0
    assert "123" in payload["stdout"]
    assert payload["stderr"] == ""
