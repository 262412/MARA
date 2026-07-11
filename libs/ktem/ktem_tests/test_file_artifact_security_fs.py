from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import ktem.index.file._scoped_page as scoped_page_module
import pytest
from ktem.index.file._scoped_page import ScopedFileIndexPageMixin
from ktem.index.file._selection_service import FileSelectionError
from theflow.settings import settings as flowsettings

from kotaemon.artifact_namespace import (
    ArtifactNamespaceError,
    finish_and_publish_artifacts,
    load_manifest_artifacts,
    write_markdown_artifact,
)

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


@pytest.mark.parametrize("mutation", ["grow", "shrink"])
def test_download_rejects_held_leaf_size_change_and_cleans_workspace(
    roots, monkeypatch, mutation
):
    leaf = _leaf(roots.markdown)
    _manifest(roots)
    original = scoped_page_module.load_manifest_artifacts

    def mutate_after_open(*args, **kwargs):
        artifacts = original(*args, **kwargs)
        if mutation == "grow":
            with leaf.open("ab") as output:
                output.write(b" GROWN")
        else:
            leaf.write_text("O", encoding="utf-8")
        return artifacts

    monkeypatch.setattr(
        scoped_page_module,
        "load_manifest_artifacts",
        mutate_after_open,
    )

    with pytest.raises(gr.Error, match="reindex"):
        _Page().download_single_file(False, FILE_ID, "owner")

    download_parent = roots.zip / "downloads" / FILE_ID
    assert not download_parent.exists() or list(download_parent.iterdir()) == []


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


def test_markdown_writer_keeps_held_namespace_when_path_is_swapped(roots, monkeypatch):
    generation_dir = roots.markdown / FILE_ID / GENERATION
    generation_dir.mkdir(parents=True)
    detached = roots.markdown / FILE_ID / "detached-generation"
    victim_dir = roots.markdown / "victim-generation"
    victim_dir.mkdir()
    victim_leaf = victim_dir / "report.md"
    victim_leaf.write_text("VICTIM", encoding="utf-8")
    real_replace = os.replace
    swapped = False

    def swap_namespace_then_replace(source, destination, *args, **kwargs):
        nonlocal swapped
        if str(destination).endswith("report.md") and not swapped:
            generation_dir.rename(detached)
            generation_dir.symlink_to(victim_dir, target_is_directory=True)
            swapped = True
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "replace", swap_namespace_then_replace)

    write_markdown_artifact(
        roots.markdown,
        "report.mhtml",
        {"file_id": FILE_ID, "artifact_generation": GENERATION},
        "OWNER",
    )

    assert swapped is True
    assert victim_leaf.read_text(encoding="utf-8") == "VICTIM"
    assert (detached / "report.md").read_text(encoding="utf-8") == "OWNER"


def test_markdown_writer_rejects_configured_root_symlink(tmp_path):
    real_root = tmp_path / "real-markdown"
    real_root.mkdir()
    configured_root = tmp_path / "configured-markdown"
    configured_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ArtifactNamespaceError):
        write_markdown_artifact(
            configured_root,
            "report.mhtml",
            {"file_id": FILE_ID, "artifact_generation": GENERATION},
            "OWNER",
        )


@pytest.mark.parametrize("linked_root", ["artifact", "manifest"])
def test_manifest_consumer_rejects_configured_root_symlink(
    roots, tmp_path, linked_root
):
    _leaf(roots.markdown)
    _manifest(roots)
    artifact_root = roots.markdown
    manifest_root = roots.zip
    if linked_root == "artifact":
        artifact_root = tmp_path / "linked-markdown"
        artifact_root.symlink_to(roots.markdown, target_is_directory=True)
    else:
        manifest_root = tmp_path / "linked-zip"
        manifest_root.symlink_to(roots.zip, target_is_directory=True)

    with pytest.raises(ArtifactNamespaceError):
        load_manifest_artifacts(
            FILE_ID,
            {"chunks": roots.chunks, "markdown": artifact_root},
            manifest_root,
        )


def test_manifest_publication_fsyncs_parent_directory(roots, tmp_path, monkeypatch):
    _leaf(roots.chunks)
    settings = SimpleNamespace(
        KH_CHUNKS_OUTPUT_DIR=str(roots.chunks),
        KH_MARKDOWN_OUTPUT_DIR=str(roots.markdown),
        KH_ZIP_OUTPUT_DIR=str(roots.zip),
    )
    pipeline = SimpleNamespace(
        _artifact_generation=GENERATION,
        _artifact_writer_future=None,
        finish=lambda *_args: None,
    )
    real_fsync = os.fsync
    fsync_modes = []

    def record_fsync(fd):
        fsync_modes.append(os.fstat(fd).st_mode)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", record_fsync)

    finish_and_publish_artifacts(
        pipeline,
        FILE_ID,
        tmp_path / "source.pdf",
        settings,
    )

    assert any(stat.S_ISDIR(mode) for mode in fsync_modes)


def test_manifest_consumer_fails_closed_without_dir_fd_support(roots, monkeypatch):
    _leaf(roots.markdown)
    _manifest(roots)
    monkeypatch.setattr(os, "supports_dir_fd", set())

    with pytest.raises(ArtifactNamespaceError, match="platform"):
        load_manifest_artifacts(
            FILE_ID,
            {"chunks": roots.chunks, "markdown": roots.markdown},
            roots.zip,
        )
