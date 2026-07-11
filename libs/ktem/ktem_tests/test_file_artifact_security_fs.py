from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import ktem.index.file._scoped_page as scoped_page_module
import pytest
from ktem.index.file._scoped_page import ScopedFileIndexPageMixin
from ktem.index.file._selection_service import FileSelectionError
from theflow.settings import settings as flowsettings

from kotaemon.artifact_namespace import write_markdown_artifact

FILE_ID = "file-owner"
GENERATION = "generation-a"


class _SelectionService:
    @staticmethod
    def source_name(file_id, user_id):
        if (file_id, user_id) != (FILE_ID, "owner"):
            raise FileSelectionError("source unavailable")
        return "report.pdf"


class _Page(ScopedFileIndexPageMixin):
    @staticmethod
    def _get_file_selection_service():
        return _SelectionService()


@pytest.fixture
def roots(tmp_path, monkeypatch):
    result = SimpleNamespace(
        chunks=tmp_path / "chunks",
        markdown=tmp_path / "markdown",
        zip=tmp_path / "zip",
    )
    for root in (result.chunks, result.markdown, result.zip):
        root.mkdir()
    monkeypatch.setattr(flowsettings, "MARA_AUTH_MODE", "auto", raising=False)
    monkeypatch.setattr(
        flowsettings, "KH_CHUNKS_OUTPUT_DIR", str(result.chunks), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_MARKDOWN_OUTPUT_DIR", str(result.markdown), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_ZIP_OUTPUT_DIR", str(result.zip), raising=False
    )
    return result


def _leaf(root: Path, content: str = "OWNER") -> Path:
    path = root / FILE_ID / GENERATION / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _manifest(roots) -> None:
    path = roots.zip / "manifests" / "v1" / FILE_ID / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "file_id": FILE_ID,
                "entries": [
                    {
                        "kind": "markdown",
                        "relative_path": (f"{FILE_ID}/{GENERATION}/report.md"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _download_path(result) -> Path:
    value = result[1].value
    return Path(value["path"] if isinstance(value, dict) else value)


def _download(page: _Page) -> tuple[list[str], str]:
    path = _download_path(page.download_single_file(False, FILE_ID, "owner"))
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        return names, archive.read(names[0]).decode("utf-8")


def test_download_rejects_hardlinked_manifest_artifact(roots):
    victim = roots.markdown / "victim-secret.md"
    victim.write_text("VICTIM", encoding="utf-8")
    leaf = roots.markdown / FILE_ID / GENERATION / "report.md"
    leaf.parent.mkdir(parents=True)
    os.link(victim, leaf)
    _manifest(roots)

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file(False, FILE_ID, "owner")


def test_download_streams_held_leaf_after_validation_swap(roots, monkeypatch):
    leaf = _leaf(roots.markdown)
    victim = roots.markdown / "victim-secret.md"
    victim.write_text("VICTIM", encoding="utf-8")
    _manifest(roots)
    original = scoped_page_module.load_manifest_artifacts

    def swap_after_open(*args, **kwargs):
        artifacts = original(*args, **kwargs)
        leaf.unlink()
        leaf.symlink_to(victim)
        return artifacts

    monkeypatch.setattr(scoped_page_module, "load_manifest_artifacts", swap_after_open)

    names, content = _download(_Page())
    assert content == "OWNER"
    assert names == ["markdown/report.md"]


def test_download_streams_held_leaf_after_intermediate_swap(roots, monkeypatch):
    leaf = _leaf(roots.markdown)
    victim_dir = roots.markdown / "victim-generation"
    victim_dir.mkdir()
    (victim_dir / leaf.name).write_text("VICTIM", encoding="utf-8")
    detached = roots.markdown / FILE_ID / "detached-generation"
    _manifest(roots)
    original = scoped_page_module.load_manifest_artifacts

    def swap_after_open(*args, **kwargs):
        artifacts = original(*args, **kwargs)
        leaf.parent.rename(detached)
        leaf.parent.symlink_to(victim_dir, target_is_directory=True)
        return artifacts

    monkeypatch.setattr(scoped_page_module, "load_manifest_artifacts", swap_after_open)

    names, content = _download(_Page())
    assert content == "OWNER"
    assert names == ["markdown/report.md"]


def test_markdown_writer_replaces_leaf_symlink_without_touching_victim(roots):
    victim = roots.markdown / "victim-secret.md"
    victim.write_text("VICTIM", encoding="utf-8")
    current_leaf = roots.markdown / FILE_ID / "report.md"
    generation_leaf = roots.markdown / FILE_ID / GENERATION / "report.md"
    current_leaf.parent.mkdir(parents=True)
    generation_leaf.parent.mkdir()
    current_leaf.symlink_to(victim)
    generation_leaf.symlink_to(victim)

    write_markdown_artifact(
        roots.markdown,
        "report.mhtml",
        {"file_id": FILE_ID, "artifact_generation": GENERATION},
        "OWNER",
    )

    assert victim.read_text(encoding="utf-8") == "VICTIM"
    assert not generation_leaf.is_symlink()
    assert generation_leaf.read_text(encoding="utf-8") == "OWNER"
