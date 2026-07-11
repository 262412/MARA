from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem.index.file._indexing_service import _quick_index_settings

from kotaemon.artifact_namespace import finish_and_publish_artifacts


def _settings(tmp_path):
    roots = SimpleNamespace(
        KH_CHUNKS_OUTPUT_DIR=str(tmp_path / "chunks"),
        KH_MARKDOWN_OUTPUT_DIR=str(tmp_path / "markdown"),
        KH_ZIP_OUTPUT_DIR=str(tmp_path / "zip"),
    )
    for value in vars(roots).values():
        Path(value).mkdir()
    return roots


def test_quick_index_settings_enable_background_writer_by_default():
    assert _quick_index_settings(7, {})["index.options.7.quick_index_mode"] is True


def test_manifest_finalization_propagates_background_writer_failure(tmp_path):
    writer: Future[None] = Future()
    writer.set_exception(RuntimeError("vector writer failed"))
    pipeline = SimpleNamespace(
        _artifact_generation="generation-a",
        _artifact_writer_future=writer,
        finish=lambda *_args: None,
    )
    settings = _settings(tmp_path)

    with pytest.raises(RuntimeError, match="vector writer failed"):
        finish_and_publish_artifacts(
            pipeline,
            "file-owner",
            tmp_path / "source.pdf",
            settings,
        )

    manifest = (
        Path(settings.KH_ZIP_OUTPUT_DIR)
        / "manifests"
        / "v1"
        / "file-owner"
        / "manifest.json"
    )
    assert not manifest.exists()


def test_manifest_finalization_waits_for_writer_before_finish(tmp_path):
    order = []

    class _CompletedWriter:
        @staticmethod
        def result():
            order.append("writer")

    pipeline = SimpleNamespace(
        _artifact_generation="generation-a",
        _artifact_writer_future=_CompletedWriter(),
        finish=lambda *_args: order.append("finish"),
    )
    settings = _settings(tmp_path)
    artifact = (
        Path(settings.KH_CHUNKS_OUTPUT_DIR)
        / "file-owner"
        / "generation-a"
        / "report_0.md"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text("OWNER", encoding="utf-8")

    finish_and_publish_artifacts(
        pipeline,
        "file-owner",
        tmp_path / "source.pdf",
        settings,
    )

    assert order == ["writer", "finish"]
