"""Thumbnail, element and graph records survive deletion of the cache peer."""

from copy import deepcopy

import pytest
from ktem.docqa.graph_builder import graph_index_from_index_documents
from ktem.docqa.multimodal_index import element_records_from_index_documents
from llama_index.core.readers.base import BaseReader

from kotaemon.base import Document

from . import indexing_backend_test_support as support

backend = support.backend


class MultimodalReader(BaseReader):
    def __init__(self):
        self.calls = 0
        self.documents = [
            Document(
                text="Alice founded Acme. Revenue 2025 was 20 million.",
                id_="text",
                metadata={
                    "page_label": "1",
                    "type": "text",
                    "file_name": "input.txt",
                },
            ),
            Document(
                text="Table: Regional revenue\nNorth 10\nSouth 12",
                id_="table",
                metadata={
                    "page_label": "1",
                    "type": "table",
                    "element_type": "table",
                    "caption": "Regional revenue",
                    "file_name": "input.txt",
                },
            ),
            Document(
                text="page thumbnail",
                id_="image",
                metadata={
                    "page_label": "1",
                    "type": "thumbnail",
                    "file_name": "input.txt",
                },
            ),
        ]

    def load_data(self, *args, **kwargs):
        self.calls += 1
        return self.documents


@pytest.mark.parametrize("stable", [False, True])
@pytest.mark.parametrize("delete_first", [0, 1])
def test_cached_multimodal_persistent_records_and_references_are_source_owned(
    backend, stable, delete_first
):
    backend.source.write_text("multimodal fixture", encoding="utf-8")
    reader = MultimodalReader()
    borrowed = deepcopy([doc.dict() for doc in reader.documents])
    producers, sources, snapshots = [], [], []
    for owner in ("alice", "bob"):
        pipeline = backend.pipeline(owner)
        pipeline.loader = reader
        pipeline.splitter = None
        pipeline.deterministic_chunk_ids = stable
        _, (identity, _) = support.drain(pipeline.stream(backend.source, False))
        producers.append(pipeline)
        sources.append(identity)
        rows = [
            row for row in support.rows(backend, "Index") if row.source_id == identity
        ]
        assert {row.relation_type for row in rows} == {
            "document",
            "vector",
            "element_index",
            "graph_index",
        }
        stored = backend.documents.get(
            [row.target_id for row in rows if row.relation_type != "vector"]
        )
        text = next(doc for doc in stored if doc.metadata["type"] == "text")
        image = next(doc for doc in stored if doc.metadata["type"] == "thumbnail")
        assert text.metadata["thumbnail_doc_id"] == image.doc_id
        assert image.metadata["file_id"] == identity
        elements = element_records_from_index_documents(stored)
        assert elements and all(record["file_id"] == identity for record in elements)
        assert all(
            record["source_backrefs"] == [f"{identity}#page:1"] for record in elements
        )
        graph = graph_index_from_index_documents(stored)
        assert graph["claims"]
        assert all(
            row["source_backrefs"] == [f"{identity}#page:1"] for row in graph["claims"]
        )
        snapshots.append([doc.dict() for doc in stored])
    assert reader.calls == 1
    assert [doc.dict() for doc in reader.documents] == borrowed
    assert set(doc["id_"] for doc in snapshots[0]).isdisjoint(
        doc["id_"] for doc in snapshots[1]
    )
    producers[delete_first].delete_file(sources[delete_first])
    retained = snapshots[1 - delete_first]
    assert [
        doc.dict() for doc in backend.documents.get([doc["id_"] for doc in retained])
    ] == retained
    assert all(
        row.source_id == sources[1 - delete_first]
        for row in support.rows(backend, "Index")
    )
