"""Owned positions survive caching; ambiguous saved targets remain unresolved."""

from copy import deepcopy

import pytest

from kotaemon.base import Document
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.performance_cache import JsonDiskCache
from kotaemon.indices.qa.citation_refs import citation_target_from_document
from kotaemon.storages import SimpleFileDocumentStore

from .pdf_navigation_test_helpers import make_pdf, reader_for


@pytest.mark.parametrize("route", ["auto", "thumbnail"])
@pytest.mark.parametrize("boundary", ["direct", "no_cache", "hit"])
def test_reserved_metadata_refused_at_every_reader_entry(tmp_path, route, boundary):
    source = make_pdf(tmp_path / "source.pdf", "duplicate")
    reader = reader_for(route)
    cache = tmp_path / "cache"
    if boundary == "hit":
        load_data_with_parse_cache(reader, source, cache_dir=cache)
    before = {p: p.read_bytes() for p in cache.rglob("*.json")}
    with pytest.raises(ValueError, match="parser-owned"):
        if boundary == "direct":
            reader.load_data(source, extra_info={"page_number": 99})
        else:
            load_data_with_parse_cache(
                reader,
                source,
                cache_dir=cache if boundary == "hit" else None,
                extra_info={"page_number": 99},
            )
    assert {p: p.read_bytes() for p in cache.rglob("*.json")} == before


@pytest.mark.parametrize("route", ["auto", "thumbnail"])
@pytest.mark.parametrize("damage", ["missing", "duplicate", "zero"])
def test_invalid_position_payload_is_reparsed(tmp_path, route, damage):
    source = make_pdf(tmp_path / "source.pdf", "duplicate")
    reader = reader_for(route)
    first = load_data_with_parse_cache(reader, source, cache_dir=tmp_path / "cache")
    cache = JsonDiskCache(tmp_path / "cache", "parse")
    assert first.cache_key is not None
    payload = cache.get(first.cache_key)
    assert isinstance(payload, dict)
    metadata = payload["documents"][1]["metadata"]
    if damage == "missing":
        metadata.pop("page_number")
    else:
        metadata["page_number"] = 1 if damage == "duplicate" else 0
    cache.set(first.cache_key, payload)
    repaired = load_data_with_parse_cache(reader, source, cache_dir=tmp_path / "cache")
    assert not repaired.cache_hit
    assert [doc.metadata["page_number"] for doc in repaired.documents[:3]] == [1, 2, 3]
    assert load_data_with_parse_cache(
        reader, source, cache_dir=tmp_path / "cache"
    ).cache_hit


@pytest.mark.parametrize("route", ["auto", "thumbnail"])
def test_policy_cannot_override_positions_and_runtime_owners_rebind(tmp_path, route):
    source = make_pdf(tmp_path / "source.pdf", "alphabetic")
    reader = reader_for(route)
    arguments = dict(
        cache_dir=tmp_path / "cache",
        reader_policy={"page_number": 99, "physical_page_policy": "invented"},
    )
    first = load_data_with_parse_cache(
        reader, source, extra_info={"owner": "A", "source_id": "A"}, **arguments
    )
    before = deepcopy([doc.to_dict() for doc in first.documents])
    second = load_data_with_parse_cache(
        reader, source, extra_info={"owner": "B", "source_id": "B"}, **arguments
    )
    assert second.cache_hit
    assert [doc.doc_id for doc in first.documents] == [
        doc.doc_id for doc in second.documents
    ]
    assert [doc.to_dict() for doc in first.documents] == before
    assert all(
        doc.metadata["owner"] == doc.metadata["source_id"] == "B"
        for doc in second.documents
    )
    assert [doc.metadata["page_number"] for doc in second.documents[:3]] == [1, 2, 3]


def test_old_persisted_known_and_ambiguous_targets_keep_identifiers(tmp_path):
    from ktem.utils.render import Render

    source = make_pdf(tmp_path / "source.pdf", "duplicate")
    saved = [
        Document(
            "old known",
            doc_id="old-known",
            metadata={
                "source_id": "old-source",
                "element_id": "old-element-1",
                "page_number": 2,
                "page_label": "8",
            },
        ),
        Document(
            "old ambiguous",
            doc_id="old-label",
            metadata={
                "source_id": "old-source",
                "element_id": "old-element-2",
                "page_label": "7",
            },
        ),
        Document(
            "old raw alias",
            doc_id="old-alias",
            metadata={
                "source_id": "old-source",
                "element_id": "old-element-3",
                "page_idx": 2,
                "page_label": "7",
            },
        ),
    ]
    for document in saved:
        document.metadata.update(file_path=str(source), file_type="application/pdf")
    before = [doc.to_dict() for doc in saved]
    store_path = tmp_path / "saved-store"
    SimpleFileDocumentStore(store_path).add(saved)
    bytes_before = {p: p.read_bytes() for p in store_path.rglob("*") if p.is_file()}
    loaded = SimpleFileDocumentStore(store_path).get([doc.doc_id for doc in saved])
    assert [doc.to_dict() for doc in loaded] == before
    targets = [citation_target_from_document(doc) for doc in loaded]
    assert [target.page_number for target in targets] == [2, None, 2]
    assert 'data-page="2"' in Render.preview("Evidence", loaded[0], "old")
    for document in loaded[1:]:
        assert "Page position unavailable" in Render.preview(
            "Evidence", document, "old"
        )
        assert 'class="pdf-link"' not in Render.preview("Evidence", document, "old")
    assert {
        p: p.read_bytes() for p in store_path.rglob("*") if p.is_file()
    } == bytes_before


def test_ambiguous_legacy_thumbnails_are_not_assigned_by_duplicate_label():
    from ktem.index.file.deterministic_chunks import prepare_chunks_for_indexing

    text = Document("old", metadata={"page_label": "7"})
    thumbnails = [Document("thumbnail", metadata={"page_label": "7"}) for _ in range(2)]
    prepare_chunks_for_indexing(
        [text], [], thumbnails, file_name="old.pdf", deterministic_chunk_ids=False
    )
    assert "thumbnail_doc_id" not in text.metadata


def test_filtered_custom_native_reader_is_not_given_guessed_positions(tmp_path):
    from llama_index.readers.file import PDFReader

    from kotaemon.loaders import AutoReader

    class FilteredReader(PDFReader):
        def load_data(self, *args, **kwargs):
            return super().load_data(*args, **kwargs)[1:]

    source = make_pdf(tmp_path / "source.pdf", "duplicate")
    reader = AutoReader(FilteredReader)
    documents = reader.load_data(source)
    assert type(reader._reader) is FilteredReader
    assert len(documents) == 2
    assert [citation_target_from_document(doc).page_number for doc in documents] == [
        None,
        None,
    ]
