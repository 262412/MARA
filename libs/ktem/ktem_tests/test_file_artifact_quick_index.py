from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem.index.file._indexing_service import _quick_index_settings

from kotaemon.artifact_namespace import finish_and_publish_artifacts
from kotaemon.artifact_pipeline import consume_in_background


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
    writer_waiting = threading.Event()
    finish_called = threading.Event()

    class _ObservedFuture(Future[None]):
        def result(self, timeout=None):
            writer_waiting.set()
            value = super().result(timeout=timeout)
            order.append("writer")
            return value

    writer = _ObservedFuture()

    def finish(*_args):
        order.append("finish")
        finish_called.set()

    pipeline = SimpleNamespace(
        _artifact_generation="generation-a",
        _artifact_writer_future=writer,
        finish=finish,
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

    manifest = (
        Path(settings.KH_ZIP_OUTPUT_DIR)
        / "manifests"
        / "v1"
        / "file-owner"
        / "manifest.json"
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        finalization = pool.submit(
            finish_and_publish_artifacts,
            pipeline,
            "file-owner",
            tmp_path / "source.pdf",
            settings,
        )
        assert writer_waiting.wait(timeout=2)
        assert not finish_called.is_set()
        assert not manifest.exists()
        writer.set_result(None)
        finalization.result(timeout=2)

    assert order == ["writer", "finish"]
    assert manifest.is_file()


def test_background_base_exception_completes_future_with_actionable_error():
    started = threading.Event()

    def exit_writer():
        started.set()
        raise SystemExit("writer exited")
        yield

    writer = consume_in_background(exit_writer)
    assert started.wait(timeout=2)

    with pytest.raises(RuntimeError, match="background writer"):
        writer.result(timeout=0.1)
    assert writer.done()
