"""Persistent identities across cache, splitter, writer and deletion modes."""

import threading
from types import SimpleNamespace

import pytest
from ktem.index.file._selection_service import FileSelectionError, FileSelectionService
from ktem.index.file.pipelines import DocumentRetrievalPipeline
from ktem.preview.context import PreviewAccess
from ktem.preview.errors import PreviewAccessError
from ktem.preview.service import PreviewService

from . import indexing_backend_test_support as support
from .test_source_write_coordination import capture

backend = support.backend


def document_targets(backend, identity):
    return [
        row.target_id
        for row in support.rows(backend, "Index")
        if row.source_id == identity and row.relation_type == "document"
    ]


@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("stable", [False, True])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("threaded", [False, True])
@pytest.mark.parametrize("delete_first", [0, 1])
def test_new_source_identity_matrix_and_survivor_access(
    backend, split, stable, cached, threaded, delete_first
):
    backend.source.write_text("isolationunique seven telescopes", encoding="utf-8")
    sources, producers = [], []
    for owner in ("alice", "bob"):
        pipeline = backend.pipeline(owner, threaded)
        if not split:
            pipeline.splitter = None
        pipeline.deterministic_chunk_ids = stable
        if not cached:
            pipeline.parse_cache_dir = None
        _, (identity, _) = support.drain(pipeline.stream(backend.source, False))
        sources.append(identity)
        producers.append(pipeline)
        assert pipeline.last_parse_cache_stats["hits"] == int(cached and owner == "bob")
    targets = [document_targets(backend, identity) for identity in sources]
    assert len(targets[0]) == len(targets[1]) == 1
    assert set(targets[0]).isdisjoint(targets[1])
    assert set(backend.vectors._collection.get()["ids"]) == set(targets[0] + targets[1])
    producers[delete_first].delete_file(sources[delete_first])
    remaining = 1 - delete_first
    owner = ("alice", "bob")[remaining]
    assert backend.vectors._collection.get()["ids"] == targets[remaining]
    assert [
        doc.doc_id for doc in backend.documents.query("isolationunique")
    ] == targets[remaining]
    retrieve = DocumentRetrievalPipeline(
        embedding=support.OwnedEmbeddings(),
        VS=backend.vectors,
        DS=backend.documents,
        Index=backend.resources["Index"],
        Source=backend.resources["Source"],
        user_id=owner,
        llm_scorer=None,
        retrieval_mode="text",
        get_extra_table=False,
    )
    docs = retrieve.run("isolationunique", doc_ids=[sources[remaining]])
    assert [doc.doc_id for doc in docs] == targets[remaining]
    assert all(doc.metadata["file_id"] == sources[remaining] for doc in docs)
    selector = FileSelectionService(
        index=backend.index, engine=backend.engine, sort_key=lambda doc: doc.doc_id
    )
    assert "isolationunique" in selector.render_chunks(sources[remaining], owner)
    with pytest.raises(FileSelectionError):
        selector.render_chunks(sources[remaining], ("alice", "bob")[delete_first])
    with pytest.raises(FileSelectionError):
        selector.render_chunks(sources[delete_first], ("alice", "bob")[delete_first])
    assert backend.source.exists()
    row = support.rows(backend, "Source")[0]
    assert (backend.resources["FileStoragePath"] / row.path).exists()
    preview = PreviewService(
        SimpleNamespace(index_manager=SimpleNamespace(indices=[backend.index])),
        engine=backend.engine,
    )
    access = PreviewAccess(user_id=owner, owner_required=True)
    source = preview.resolve_source(sources[remaining], access=access)
    assert source.path.read_text() == "isolationunique seven telescopes"
    with pytest.raises(PreviewAccessError):
        preview.resolve_source(sources[delete_first], access=access)
    with pytest.raises(PreviewAccessError):
        preview.resolve_source(
            sources[remaining],
            access=PreviewAccess(
                user_id=("alice", "bob")[delete_first], owner_required=True
            ),
        )


def test_old_source_delete_same_name_new_source_then_old_writer_cannot_cross_write(
    backend, monkeypatch
):
    backend.source.write_text("incarnationunique old", encoding="utf-8")
    old = backend.pipeline()
    old.splitter = None
    entered, release = threading.Event(), threading.Event()
    embed = old.vector_indexing._embed_documents

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(15)
        return embed(*args, **kwargs)

    monkeypatch.setattr(old.vector_indexing, "_embed_documents", paused)
    errors: list[BaseException] = []
    worker = threading.Thread(
        target=capture, args=(errors, lambda: list(old.stream(backend.source, False)))
    )
    try:
        worker.start()
        assert entered.wait(10)
        old_id = support.rows(backend, "Source")[0].id
        backend.pipeline().delete_file(old_id)
        new = backend.pipeline()
        new.splitter = None
        _, (new_id, _) = support.drain(new.stream(backend.source, False))
        assert new_id != old_id
        assert new.last_parse_cache_stats["hits"] == 1
        targets = document_targets(backend, new_id)
    finally:
        release.set()
        worker.join(20)
        assert not worker.is_alive()
    assert len(errors) == 1 and "Source removed during indexing" in str(errors[0])
    assert [row.id for row in support.rows(backend, "Source")] == [new_id]
    assert {row.source_id for row in support.rows(backend, "Index")} == {new_id}
    assert backend.vectors._collection.get()["ids"] == targets
    assert [
        doc.doc_id for doc in backend.documents.query("incarnationunique")
    ] == targets
