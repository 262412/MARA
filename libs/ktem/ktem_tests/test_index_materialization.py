"""New-write IDs are scoped independently of shared parser/cache identities."""

from copy import deepcopy

import pytest
from ktem.index.file.deterministic_chunks import prepare_chunks_for_indexing
from ktem.index.file.index_materialization import materialize_index_chunks
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo

from kotaemon.base import Document


def materialize(
    documents, *, namespace="index__205__source", source="source-a", stable=False
):
    return materialize_index_chunks(
        documents,
        namespace=namespace,
        file_id=source,
        file_name="same.pdf",
        splitter=None,
        deterministic_chunk_ids=stable,
        prepare_chunks=prepare_chunks_for_indexing,
    )


def documents():
    return [
        Document(
            text="Alpha",
            id_="parser-text",
            source="parser-image",
            metadata={
                "type": "text",
                "page_label": "1",
                "nested": {"values": [1]},
            },
            relationships={
                NodeRelationship.NEXT: RelatedNodeInfo(node_id="parser-image"),
                NodeRelationship.SOURCE: RelatedNodeInfo(node_id="parser-parent"),
                NodeRelationship.CHILD: [RelatedNodeInfo(node_id="parser-image")],
            },
        ),
        Document(
            text="image",
            id_="parser-image",
            metadata={
                "type": "thumbnail",
                "page_label": "1",
            },
        ),
    ]


def test_exact_new_persistent_ids_thumbnail_relationships_and_borrowed_ownership():
    borrowed = documents()
    original = deepcopy([doc.dict() for doc in borrowed])
    result = materialize(borrowed)
    text_id = "index-chunk:v1:12478089157775b61c1bf45d664a1d9c1fd7b01dc2c7d45a7b6f22298389a471"
    image_id = "index-chunk:v1:56ec835e4a25b615b870c7165d16a074fbfa79d6459a54e239078e742c71ca94"
    parent_id = "index-chunk:v1:66cd97dd528bad6a60450563eda9f54fa7b64c2f101565f60a201c1f9496faff"
    assert [doc.doc_id for doc in result] == [text_id, image_id]
    assert result[0].metadata["thumbnail_doc_id"] == image_id
    assert result[0].source == image_id
    assert result[0].relationships[NodeRelationship.NEXT].node_id == image_id
    assert result[0].relationships[NodeRelationship.SOURCE].node_id == parent_id
    assert result[0].relationships[NodeRelationship.CHILD][0].node_id == image_id
    assert [doc.metadata["file_id"] for doc in result] == ["source-a", "source-a"]
    result[0].metadata["nested"]["values"].append(2)
    assert [doc.dict() for doc in borrowed] == original


@pytest.mark.parametrize("stable", [False, True])
def test_namespace_and_source_are_independent_and_same_inputs_repeat(stable):
    borrowed = documents()
    first = materialize(borrowed, stable=stable)
    assert [doc.dict() for doc in first] == [
        doc.dict() for doc in materialize(borrowed, stable=stable)
    ]
    for kwargs in ({"source": "source-b"}, {"namespace": "index__206__source"}):
        other = materialize(borrowed, stable=stable, **kwargs)
        assert not {doc.doc_id for doc in first}.intersection(
            doc.doc_id for doc in other
        )
        text = next(doc for doc in other if doc.metadata["type"] == "text")
        thumbnail = next(doc for doc in other if doc.metadata["type"] == "thumbnail")
        assert text.metadata["thumbnail_doc_id"] == thumbnail.doc_id
        assert text.relationships[NodeRelationship.NEXT].node_id == thumbnail.doc_id


def test_original_prepare_patch_is_consumed_once_after_split_without_resorting():
    calls: list[tuple] = []
    borrowed = documents()

    def split(docs):
        calls.append(("split", [doc.doc_id for doc in docs]))
        docs[0].metadata["nested"]["values"].append(2)
        return docs

    def prepare(text, other, thumbnails, **kwargs):
        calls.append(("prepare", [doc.doc_id for doc in text], kwargs))
        return [*thumbnails, *text]

    result = materialize_index_chunks(
        borrowed,
        namespace="index",
        file_id="source",
        file_name="same.pdf",
        splitter=split,
        deterministic_chunk_ids=False,
        prepare_chunks=prepare,
    )
    assert calls == [
        ("split", ["parser-text"]),
        (
            "prepare",
            ["parser-text"],
            {"file_name": "same.pdf", "deterministic_chunk_ids": False},
        ),
    ]
    assert [doc.text for doc in result] == ["image", "Alpha"]
    assert borrowed[0].metadata["nested"] == {"values": [1]}
