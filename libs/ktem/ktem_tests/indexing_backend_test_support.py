"""Exclusive SQL, Chroma and Lance resources for producer lifecycle checks."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from ktem.index.file import index as index_module
from ktem.index.file import pipelines
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from kotaemon.base import DocumentWithEmbedding
from kotaemon.embeddings.base import BaseEmbeddings
from kotaemon.indices.splitters import TokenSplitter
from kotaemon.loaders.txt_loader import TxtReader
from kotaemon.storages import LanceDBDocumentStore

owned_chroma_stores = import_module(
    "libs.kotaemon.tests.chroma_test_runtime"
).owned_chroma_stores


class OwnedEmbeddings(BaseEmbeddings):
    def invoke(self, text, **kwargs):
        return [
            DocumentWithEmbedding(content=doc, embedding=[1.0, 0.0, 0.0])
            for doc in self.prepare_input(text)
        ]


@pytest.fixture
def backend(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'indexing.sqlite'}")
    documents = LanceDBDocumentStore(
        str(tmp_path / "lance"), collection_name="r5b_owned_documents"
    )
    monkeypatch.setattr(pipelines, "engine", engine)
    monkeypatch.setattr(index_module, "filestorage_path", tmp_path / "storage")
    monkeypatch.setattr(
        pipelines.settings, "KH_FILE_INDEX_ARTIFACTS_ENABLED", False, raising=False
    )
    produced = []
    with owned_chroma_stores(tmp_path) as create:
        vectors = create(collection_name="r5b-owned-vectors")
        monkeypatch.setattr(index_module, "get_vectorstore", lambda _: vectors)
        monkeypatch.setattr(index_module, "get_docstore", lambda _: documents)
        index = index_module.FileIndex(None, 205, "owned lifecycle", {"private": True})
        resources = index._resources
        resources["Source"].metadata.create_all(engine)

        def pipeline(owner="alice", threaded=True):
            result = pipelines.IndexPipeline(
                loader=TxtReader(),
                splitter=TokenSplitter(chunk_size=1024, chunk_overlap=256),
                embedding=OwnedEmbeddings(),
                Source=resources["Source"],
                Index=resources["Index"],
                VS=vectors,
                DS=documents,
                FSPath=resources["FileStoragePath"],
                user_id=owner,
                private=True,
                run_embedding_in_thread=threaded,
                parse_cache_dir=str(tmp_path / "parse"),
            )
            # The bounded runtime supports artifact-disabled operation. Shared
            # backend/cache handles remain open until this fixture's users exit.
            result.vector_indexing.cache_dir = None
            result.vector_indexing.embedding_cache_dir = str(tmp_path / "embeddings")
            produced.append(result)
            return result

        try:
            yield SimpleNamespace(
                engine=engine,
                resources=resources,
                documents=documents,
                vectors=vectors,
                pipeline=pipeline,
                source=tmp_path / "input.txt",
            )
        finally:
            for result in produced:
                writer = getattr(result, "_artifact_writer_future", None)
                if writer is not None:
                    writer.thread.join(5)
                    assert not writer.thread.is_alive()
            if documents.collection_name in documents.db_connection.table_names():
                documents.drop()
            engine.dispose()


def rows(backend, key):
    with Session(backend.engine) as session:
        return list(session.scalars(select(backend.resources[key])))


def drain(stream):
    events = []
    while True:
        try:
            events.append(next(stream))
        except StopIteration as stopped:
            return events, stopped.value
