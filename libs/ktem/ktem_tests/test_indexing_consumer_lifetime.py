from concurrent.futures import CancelledError
from importlib import import_module
from types import SimpleNamespace
from typing import Any, cast

import pytest
from ktem.docqa import _runtime_indexing as runtime
from ktem.index.file import _indexing_service as web


class RetainedStream:
    def __init__(self, error=None):
        self.error = error
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.error:
            raise self.error
        return SimpleNamespace(channel="debug", text="progress")

    def close(self):
        self.closed = True


def service(tmp_path, stream):
    pipeline = SimpleNamespace(stream=lambda *a, **kw: stream)
    return web.FileIndexingService(
        index=SimpleNamespace(
            id=7, config={}, get_indexing_pipeline=lambda *a: pipeline
        ),
        supported_file_types=[".txt"],
        zip_input_dir=tmp_path / "zip",
        engine=None,
        demo_mode=False,
        notify=lambda *a: None,
    )


def test_web_close_reaches_retained_inner_stream(tmp_path):
    stream = RetainedStream()
    updates = service(tmp_path, stream)._stream_index(
        ["file"], reindex=False, settings={}, user_id="owner"
    )
    assert next(updates) == ("", "progress")
    updates.close()
    assert stream.closed


def test_runtime_capture_error_closes_inner_stream(monkeypatch):
    stream = RetainedStream()
    error = ValueError("capture failed")

    def capture(*args):
        raise error

    monkeypatch.setattr(runtime, "_capture_indexing_response", capture)
    with pytest.raises(ValueError) as caught:
        runtime._consume_indexing_stream(
            SimpleNamespace(stream=lambda *a, **kw: stream), ["file"], False
        )
    assert caught.value is error
    assert stream.closed


def test_quick_drain_interrupt_closes_owned_updates():
    error = KeyboardInterrupt("cancel")
    stream = RetainedStream(error)
    with pytest.raises(KeyboardInterrupt) as caught:
        web._drain_updates(cast(Any, stream))
    assert caught.value is error
    assert stream.closed


def test_web_does_not_convert_producer_cancellation_to_file_failure(tmp_path):
    stream = RetainedStream(CancelledError("cancelled producer"))
    updates = service(tmp_path, stream)._stream_index(
        ["file"], reindex=False, settings={}, user_id="owner"
    )
    with pytest.raises(CancelledError, match="cancelled producer"):
        next(updates)
    assert stream.closed


@pytest.mark.parametrize("entry", ["cli", "sidecar"])
def test_application_entry_interrupt_reaches_real_runtime_file_service(
    tmp_path, monkeypatch, entry
):
    from ktem.docqa._runtime_file_service import RuntimeFileService

    stream = RetainedStream(KeyboardInterrupt("cancel"))
    file_index = SimpleNamespace(
        config={"supported_file_types": ".txt"},
        get_indexing_pipeline=lambda *args: SimpleNamespace(
            stream=lambda *a, **kw: stream
        ),
    )
    runtime_service = RuntimeFileService(
        file_index=file_index,
        engine=None,
        resolve_user_id=lambda user: "owner",
        load_settings=lambda user: {},
        zip_input_dir=str(tmp_path / "zip"),
    )
    if entry == "cli":
        from click.testing import CliRunner

        docqa_cli = import_module("slide_cli.docqa_cli")

        monkeypatch.setattr(docqa_cli, "create_docqa_runtime", lambda: runtime_service)
        result = CliRunner().invoke(docqa_cli.docqa, ["index", "https://owned"])
        assert result.exit_code == 1
        assert "Aborted" in result.output
    else:
        application = import_module(
            "apps.desktop.sidecar.application"
        ).DesktopApplicationService(create_runtime=lambda: runtime_service)
        with pytest.raises(KeyboardInterrupt, match="cancel"):
            application.index_files(["https://owned"])
    assert stream.closed
