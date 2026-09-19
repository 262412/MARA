import threading

import pytest
from ktem.index.file import pipelines
from ktem.index.file.deletion import DeletionCoordinator

from kotaemon import artifact_namespace

from . import indexing_backend_test_support as support

backend = support.backend


@pytest.mark.parametrize("threaded", [False, True])
def test_actual_store_writes_finish_cache_replay_and_two_owners(backend, threaded):
    backend.source.write_text(
        "ownedunique report about seven telescopes", encoding="utf-8"
    )
    ids, paths = [], []
    for owner in ("alice", "bob"):
        pipeline = backend.pipeline(owner, threaded)
        events, (identity, docs) = support.drain(pipeline.stream(backend.source, False))
        assert events[-1].text == " => Finished indexing input.txt"
        assert all("artifact_generation" not in doc.metadata for doc in docs)
        source = next(
            row for row in support.rows(backend, "Source") if row.id == identity
        )
        ids.append(identity)
        paths.append(source.path)
        assert source.user == owner and source.note["loader"] == "TxtReader"
        assert source.note["tokens"] > 0
        assert (backend.resources["FileStoragePath"] / source.path).exists()
        if owner == "bob":
            assert pipeline.last_parse_cache_stats["hits"] == 1
    assert ids[0] != ids[1] and paths[0] == paths[1]
    relations = support.rows(backend, "Index")
    assert len(relations) == 4
    assert [row.user for row in relations] == ["alice", "alice", "bob", "bob"]
    vectors = backend.vectors._collection.get()["ids"]
    assert set(vectors) == {
        row.target_id for row in relations if row.relation_type == "vector"
    }
    assert len(backend.documents.query("ownedunique")) == 2
    assert backend.source.exists()


@pytest.mark.parametrize("failure", ["vector", "finish", "manifest"])
def test_partial_persistent_state_is_not_rolled_back_or_reported_success(
    backend, monkeypatch, failure
):
    backend.source.write_text("partialunique input", encoding="utf-8")
    pipeline = backend.pipeline()
    error = RuntimeError(f"owned {failure} failure")

    def fail(*args, **kwargs):
        raise error

    if failure == "vector":
        original = type(backend.vectors).add

        def partial(*args, **kwargs):
            original(*args, **kwargs)
            raise error

        monkeypatch.setattr(type(backend.vectors), "add", partial)
    elif failure == "finish":
        monkeypatch.setattr(pipelines.IndexPipeline, "finish", fail)
    else:
        monkeypatch.setattr(pipelines.settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", True)
        monkeypatch.setattr(artifact_namespace, "publish_runtime_manifest", fail)
    events = []
    with pytest.raises(RuntimeError) as caught:
        for event in pipeline.stream(backend.source, False):
            events.append(event)
    assert caught.value is error
    assert not any("Finished indexing" in event.text for event in events)
    assert len(support.rows(backend, "Source")) == 1
    assert len(backend.documents.query("partialunique")) == 1
    assert len(backend.vectors._collection.get()["ids"]) == 1
    relations = support.rows(backend, "Index")
    assert [row.relation_type for row in relations] == (
        ["document"] if failure == "vector" else ["document", "vector"]
    )
    source = support.rows(backend, "Source")[0]
    assert ("loader" in source.note) is (failure == "manifest")
    assert (backend.resources["FileStoragePath"] / source.path).exists()
    assert not pipeline._artifact_writer_future.thread.is_alive()


def test_delete_during_writer_exposes_unfenced_external_write_blocker(
    backend, monkeypatch, request
):
    """Characterize the remaining blocker, not an atomic-delete safety proof."""
    backend.source.write_text("lateunique input", encoding="utf-8")
    pipeline = backend.pipeline()
    entered, release = threading.Event(), threading.Event()
    original = pipeline.vector_indexing._embed_documents

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline.vector_indexing, "_embed_documents", blocked)
    failures, events = [], []

    def consume():
        try:
            events.extend(pipeline.stream(backend.source, False))
        except Exception as exc:
            failures.append(exc)

    consumer = threading.Thread(target=consume)
    try:
        consumer.start()
        assert entered.wait(10)
        source = support.rows(backend, "Source")[0]
        DeletionCoordinator(
            engine=backend.engine,
            source_table=backend.resources["Source"],
            index_table=backend.resources["Index"],
            vector_store=backend.vectors,
            doc_store=backend.documents,
            file_storage_path=backend.resources["FileStoragePath"],
        ).delete(source.id, user_id="alice")
        assert support.rows(backend, "Source") == []
        assert support.rows(backend, "Index") == []
        assert backend.documents.query("lateunique") == []
    finally:
        release.set()
        consumer.join(10)
        assert not consumer.is_alive()
    assert len(failures) == 1
    assert "Source removed during indexing" in str(failures[0])
    assert not any("Finished indexing" in event.text for event in events)
    assert support.rows(backend, "Source") == []
    assert len(backend.vectors._collection.get()["ids"]) == 1
    assert [row.relation_type for row in support.rows(backend, "Index")] == ["vector"]
    request.node.user_properties.append(
        (
            "r5b_remaining_blocker",
            "deleted source has late vector and SQL relation; no producer/delete fencing",
        )
    )
