from concurrent.futures import CancelledError
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, cast

import pytest
from ktem.index.file import pipelines
from ktem.index.file.pipelines import IndexDocumentPipeline, IndexPipeline

from kotaemon import artifact_pipeline as artifacts
from kotaemon.base import Document


def drain(iterator):
    events = []
    while True:
        try:
            item = next(iterator)
            events.append((item.channel, item.content))
        except StopIteration as stop:
            return events, stop.value


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("reindex", [False, True])
def test_single_stream_original_order_metadata_and_return(
    tmp_path, monkeypatch, cached, reindex
):
    monkeypatch.setattr(
        pipelines.settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", False, raising=False
    )
    original, parsed = tmp_path / "original.docx", tmp_path / "converted.pdf"
    original.write_text("original")
    parsed.write_text("parse")
    calls: list[tuple] = []
    docs = [Document(text="body", metadata={"artifact_generation": "temporary"})]
    subject = SimpleNamespace(collection_name="collection")
    subject.source_write_scope = lambda _file_id: nullcontext()

    def lookup(path):
        calls.append(("lookup", path))
        return "old" if reindex else None

    def store(path):
        calls.append(("source", path))
        return "new"

    subject.get_id_if_exists = lookup
    subject.delete_file = lambda identity: calls.append(("delete", identity))
    subject.store_file = store

    def parse(path, metadata):
        calls.append(("parse", path))
        assert metadata["file_id"] == "new"
        assert metadata["collection_name"] == "collection"
        assert metadata["layout"] == "preserved"
        return SimpleNamespace(
            documents=docs,
            cache_hit=cached,
            stats={"hits": int(cached), "misses": int(not cached), "writes": 0},
        )

    def handle(documents, identity, name, generation):
        assert documents is docs
        assert docs[0].metadata == {}
        calls.append(("handle", identity, name, generation))
        yield Document("written", channel="debug")

    subject.load_docs_with_parse_cache = parse
    subject.handle_docs = handle
    subject.finish = lambda *args: calls.append(("finish", *args))
    events, result = drain(
        IndexPipeline.stream(
            subject,
            parsed,
            reindex,
            source_file_path=original,
            source_file_name="original.docx",
            layout_metadata={"layout": "preserved"},
        )
    )
    expected: list[tuple] = [("lookup", original)]
    if reindex:
        expected.append(("delete", "old"))
    expected.extend(
        [
            ("source", original),
            ("parse", parsed),
            ("handle", "new", "original.docx", None),
            ("finish", "new", original),
        ]
    )
    assert calls == expected
    assert result[0] == "new" and result[1] is docs
    texts = [content for channel, content in events]
    assert all(channel == "debug" for channel, _ in events)
    assert texts == ([" => Removing old original.docx"] if reindex else []) + [
        " => Converting original.docx to text",
        f" => Converted original.docx to text (parse cache {'hit' if cached else 'miss'}; hits={int(cached)}, misses={int(not cached)}, writes=0)",
        "written",
        " => Finished indexing original.docx",
    ]


@pytest.mark.parametrize(
    "failure", [ValueError("bad file"), KeyboardInterrupt("cancel")]
)
def test_batch_exception_continues_but_termination_does_not(failure):
    calls = []
    docs = [Document(text="second")]

    def stream(path, **kwargs):
        calls.append((path, kwargs))
        if path == "https://first":
            raise failure
        yield Document("writer", channel="debug")
        return "second", docs

    subject = SimpleNamespace(
        is_url=lambda path: True, route=lambda _: SimpleNamespace(stream=stream)
    )
    batch = IndexDocumentPipeline.stream(
        cast(Any, subject), ["https://first", "https://second"], reindex=True
    )
    if isinstance(failure, Exception):
        events, result = drain(batch)
        assert result == ([None, "second"], ["bad file", None], docs)
        assert events == [
            ("debug", "Indexing [1/2]: https://first"),
            (
                "index",
                {
                    "file_path": "https://first",
                    "file_name": "https://first",
                    "status": "failed",
                    "message": "bad file",
                },
            ),
            ("debug", "Indexing [2/2]: https://second"),
            ("debug", "writer"),
            (
                "index",
                {
                    "file_path": "https://second",
                    "file_name": "https://second",
                    "status": "success",
                },
            ),
        ]
        assert len(calls) == 2
    else:
        with pytest.raises(KeyboardInterrupt) as caught:
            drain(batch)
        assert caught.value is failure
        assert len(calls) == 1
    assert calls[0][1] == {
        "reindex": True,
        "source_file_path": None,
        "source_file_name": "https://first",
        "layout_metadata": None,
    }


def test_batch_does_not_continue_after_cancelled_producer():
    calls = []

    def stream(path, **kwargs):
        calls.append(path)
        raise CancelledError("cancelled producer")
        yield

    subject = SimpleNamespace(
        is_url=lambda path: True, route=lambda _: SimpleNamespace(stream=stream)
    )
    with pytest.raises(CancelledError, match="cancelled producer"):
        drain(
            IndexDocumentPipeline.stream(
                cast(Any, subject), ["https://first", "https://second"]
            )
        )
    assert calls == ["https://first"]


@pytest.mark.parametrize("termination", [GeneratorExit, KeyboardInterrupt])
def test_background_termination_cannot_become_a_recoverable_file_error(termination):
    calls = []
    error = termination("owned producer terminated")

    def produce():
        raise error

    def stream(path, **kwargs):
        calls.append(path)
        pipeline = SimpleNamespace(
            run_embedding_in_thread=True, finish=lambda *args: pytest.fail()
        )
        artifacts.schedule_writer(pipeline, produce)
        writer = pipeline._artifact_writer_future
        try:
            artifacts.finish_indexing(pipeline, "file", path)
            yield Document("unreachable", channel="debug")
        finally:
            writer.thread.join(5)
            assert not writer.thread.is_alive()

    subject = SimpleNamespace(
        is_url=lambda path: True, route=lambda _: SimpleNamespace(stream=stream)
    )
    with pytest.raises(termination) as caught:
        drain(
            IndexDocumentPipeline.stream(
                cast(Any, subject), ["https://first", "https://second"]
            )
        )
    assert caught.value is error
    assert calls == ["https://first"]
