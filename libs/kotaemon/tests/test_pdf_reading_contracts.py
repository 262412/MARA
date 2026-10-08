"""Real PDF parsing and owned persistence contracts for reader-stack upgrades."""

import base64
import importlib
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from llama_index.readers.file import PDFReader
from openai.types.create_embedding_response import CreateEmbeddingResponse
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError
from tenacity import RetryError

from kotaemon.base import Document
from kotaemon.embeddings import AzureOpenAIEmbeddings
from kotaemon.indices import VectorIndexing
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.qa.citation_refs import citation_target_from_document
from kotaemon.loaders import AutoReader, PDFThumbnailReader
from kotaemon.storages import (
    LanceDBDocumentStore,
    SimpleFileDocumentStore,
    SimpleFileVectorStore,
)

PAGE_TEXT = ["Alpha page one", "Beta page two", "Gamma page three"]
PAGE_COLORS = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]


def write_pdf(path: Path, labels=None, *, encrypted=False):
    with fitz.open() as document:
        for text, color in zip(PAGE_TEXT, PAGE_COLORS):
            page = document.new_page(width=216, height=144)
            page.draw_rect(page.rect, color=color, fill=color)
            page.insert_text((20, 40), text, fontsize=10, color=(0, 0, 0))
        document.set_metadata({"title": "Owned PDF contract", "author": "Fixture"})
        if labels is not None:
            document.set_page_labels(labels)
        options = (
            {
                "encryption": fitz.PDF_ENCRYPT_AES_256,
                "owner_pw": "fixture-owner",
                "user_pw": "fixture-reader",
            }
            if encrypted
            else {}
        )
        document.save(path, **options)
    return path


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        (None, ["1", "2", "3"]),
        ([{"startpage": 0, "style": "D", "firstpagenum": 7}], ["7", "8", "9"]),
        ([{"startpage": 0, "style": "r", "firstpagenum": 1}], ["i", "ii", "iii"]),
        ([{"startpage": 0, "style": "A", "firstpagenum": 1}], ["A", "B", "C"]),
        ([{"startpage": 0, "style": "A", "firstpagenum": 27}], ["AA", "BB", "CC"]),
        (
            [{"startpage": 0, "style": "D", "prefix": "App-", "firstpagenum": 1}],
            ["App-1", "App-2", "App-3"],
        ),
    ],
    ids=[
        "physical",
        "offset-digits",
        "roman",
        "alphabetical",
        "past-z-official619",
        "prefix",
    ],
)
def test_real_pdf_page_order_text_labels_and_metadata(tmp_path, labels, expected):
    source = write_pdf(tmp_path / "report.pdf", labels)
    extra = {"source_id": "owned-source", "file_id": "owned-file"}
    documents = AutoReader("PDFReader").load_data(source, extra_info=extra)

    assert [document.text.strip() for document in documents] == PAGE_TEXT
    assert [document.metadata["page_label"] for document in documents] == expected
    assert all(isinstance(document, Document) for document in documents)
    assert len({document.doc_id for document in documents}) == 3
    assert all(
        document.metadata
        == {
            "file_name": "report.pdf",
            "page_label": label,
            "page_number": position,
            **extra,
        }
        for position, (document, label) in enumerate(zip(documents, expected), 1)
    )
    assert PdfReader(source).metadata.title == "Owned PDF contract"
    full = PDFReader(return_full_document=True).load_data(source, extra_info=extra)
    assert len(full) == 1
    assert full[0].text.split() == " ".join(PAGE_TEXT).split()
    assert full[0].metadata == {"file_name": "report.pdf", **extra}


@pytest.mark.parametrize("style", ["D", "r", "A"])
def test_thumbnail_reader_preserves_display_labels_and_physical_pages(tmp_path, style):
    """The closeout fixes the frozen 4E filter that lost non-numeric pages."""
    source = write_pdf(
        tmp_path / "labels.pdf",
        [{"startpage": 0, "style": style, "firstpagenum": 1}],
    )
    documents = PDFThumbnailReader().load_data(source, extra_info={"file_id": "f"})
    text, thumbnails = documents[:3], documents[3:]
    assert [document.text.strip() for document in text] == PAGE_TEXT
    assert [document.metadata["page_label"] for document in thumbnails] == PdfReader(
        source
    ).page_labels
    assert [document.metadata["page_number"] for document in text] == [1, 2, 3]
    assert [document.metadata["page_number"] for document in thumbnails] == [1, 2, 3]
    for thumbnail, expected_color in zip(thumbnails, PAGE_COLORS):
        assert thumbnail.metadata["type"] == "thumbnail"
        assert thumbnail.metadata["file_id"] == "f"
        prefix, data = thumbnail.metadata["image_origin"].split(",", 1)
        assert prefix == "data:image/png;base64"
        with Image.open(BytesIO(base64.b64decode(data))) as image:
            assert image.size == (120, 80)
            assert image.getpixel((5, 5)) == tuple(
                int(value * 255) for value in expected_color
            )


def test_encrypted_pdf_requires_password_and_retains_page_order(tmp_path):
    source = write_pdf(tmp_path / "encrypted.pdf", encrypted=True)
    with pytest.raises(RetryError) as failure:
        AutoReader("PDFReader").load_data(source)
    assert isinstance(failure.value.last_attempt.exception(), FileNotDecryptedError)
    reader = PdfReader(source, password="fixture-reader")
    assert [page.extract_text().strip() for page in reader.pages] == PAGE_TEXT


@pytest.mark.parametrize("payload", [b"", b"not a PDF", b"%PDF-1.4\n1 0 obj\n<<"])
def test_bad_pdf_reports_parser_failure_without_partial_documents(tmp_path, payload):
    source = tmp_path / "bad.pdf"
    source.write_bytes(payload)
    with pytest.raises(RetryError) as failure:
        AutoReader("PDFReader").load_data(source)
    assert isinstance(failure.value.last_attempt.exception(), PdfReadError)


def test_real_pdf_parse_cache_reloads_ids_text_and_current_path(tmp_path):
    source = write_pdf(tmp_path / "first.pdf")
    renamed = tmp_path / "renamed.pdf"
    renamed.write_bytes(source.read_bytes())
    cache = tmp_path / "parse-cache"
    first = load_data_with_parse_cache(
        AutoReader("PDFReader"),
        source,
        cache_dir=cache,
        extra_info={"file_id": "first-source"},
    )
    second = load_data_with_parse_cache(
        AutoReader("PDFReader"),
        renamed,
        cache_dir=cache,
        extra_info={"file_id": "second-source"},
    )
    assert not first.cache_hit
    assert second.cache_hit
    assert second.cache_key == first.cache_key
    assert [doc.doc_id for doc in second.documents] == [
        doc.doc_id for doc in first.documents
    ]
    assert [doc.text.strip() for doc in second.documents] == PAGE_TEXT
    assert all(doc.content == doc.text for doc in second.documents)
    assert all(doc.metadata["file_name"] == "renamed.pdf" for doc in second.documents)
    assert all(doc.metadata["file_id"] == "second-source" for doc in second.documents)
    assert second.stats == {"hits": 1, "misses": 0, "writes": 0}


def _embedding_response(*args, **kwargs):
    """Use the existing OpenAI API test seam; parser and stores remain real."""
    texts = kwargs["input"]
    if isinstance(texts, str):
        texts = [texts]
    return CreateEmbeddingResponse(
        data=[
            {"object": "embedding", "index": index, "embedding": [1.0, 0.0, 0.0]}
            for index, _ in enumerate(texts)
        ],
        model="pdf-contract-fixture",
        object="list",
        usage={"prompt_tokens": 0, "total_tokens": 0},
    )


def test_real_pdf_owned_index_reload_citations_and_embedding_cache(tmp_path):
    source = write_pdf(tmp_path / "index.pdf")
    documents = AutoReader("PDFReader").load_data(
        source,
        extra_info={"source_id": "source", "file_id": "file"},
    )
    for index, document in enumerate(documents, 1):
        document.doc_id = f"pdf-page-{index}"
    embedding = AzureOpenAIEmbeddings(
        azure_deployment="pdf-fixture",
        azure_endpoint="https://fixture.invalid/",
        api_key="fixture-key",
        api_version="fixture-version",
    )
    doc_path, vector_path = tmp_path / "documents", tmp_path / "vectors"
    document_store = SimpleFileDocumentStore(doc_path)
    vector_store = SimpleFileVectorStore(vector_path)
    pipeline = VectorIndexing(
        vector_store=vector_store,
        doc_store=document_store,
        embedding=embedding,
        cache_dir=str(tmp_path / "chunks"),
        embedding_cache_dir=str(tmp_path / "embeddings"),
        index_contract="pdf-contract-v1",
    )
    with patch(
        "openai.resources.embeddings.Embeddings.create", side_effect=_embedding_response
    ) as create:
        pipeline(documents)
        assert create.call_count == 1
        assert pipeline.last_embedding_cache_stats == {
            "hits": 0,
            "misses": 3,
            "writes": 3,
        }
        replica = VectorIndexing(
            vector_store=SimpleFileVectorStore(tmp_path / "replica-vectors"),
            doc_store=SimpleFileDocumentStore(tmp_path / "replica-documents"),
            embedding=embedding,
            cache_dir=str(tmp_path / "replica-chunks"),
            embedding_cache_dir=str(tmp_path / "embeddings"),
            index_contract="pdf-contract-v1",
        )
        replica(documents)
        assert create.call_count == 1
        assert replica.last_embedding_cache_stats == {
            "hits": 3,
            "misses": 0,
            "writes": 0,
        }

    ids = [document.doc_id for document in documents]
    reloaded = SimpleFileDocumentStore(doc_path).get(ids)
    assert [doc.to_dict() for doc in reloaded] == [
        doc.to_dict() for doc in document_store.get(ids)
    ]
    persisted = json.loads((doc_path / "default.json").read_text())
    assert list(persisted) == ids
    assert [persisted[key]["text"].strip() for key in ids] == PAGE_TEXT
    reopened_vectors = SimpleFileVectorStore(vector_path)
    assert set(reopened_vectors.query([1.0, 0.0, 0.0], top_k=3)[2]) == set(ids)
    for index, document in enumerate(reloaded, 1):
        target = citation_target_from_document(document)
        assert target.doc_id == f"pdf-page-{index}"
        assert target.source_id == "source"
        assert target.page_label == str(index)
        assert target.element_id == document.metadata["element_id"]


def test_real_pdf_configured_qdrant_lance_stores_survive_reopen(tmp_path):
    from .qdrant_test_runtime import owned_qdrant_stores

    documents = AutoReader("PDFReader").load_data(write_pdf(tmp_path / "stored.pdf"))
    ids = [document.doc_id for document in documents]
    doc_path, vector_path = tmp_path / "lance", tmp_path / "qdrant"
    store = LanceDBDocumentStore(path=str(doc_path), collection_name="owned_pdf")
    store.add(documents)
    with owned_qdrant_stores(tmp_path) as create:
        vectors = create(path=vector_path)
        vectors.add(
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            metadatas=[document.metadata for document in documents],
            ids=ids,
        )
    reopened = LanceDBDocumentStore(path=str(doc_path), collection_name="owned_pdf")
    documents_by_id = {doc.doc_id: doc for doc in reopened.get(ids)}
    assert [documents_by_id[key].text.strip() for key in ids] == PAGE_TEXT
    assert [documents_by_id[key].metadata["page_label"] for key in ids] == [
        "1",
        "2",
        "3",
    ]
    with owned_qdrant_stores(tmp_path, cleanup=True) as create:
        vectors = create(path=vector_path)
        assert vectors.count() == 3
        assert vectors.query([1.0, 0.0, 0.0], top_k=1)[2] == ids[:1]


@pytest.mark.parametrize(
    "classpath",
    [
        "kotaemon.loaders.PDFThumbnailReader",
        "kotaemon.storages.ChromaVectorStore",
        "kotaemon.storages.LanceDBVectorStore",
        "kotaemon.storages.MilvusVectorStore",
        "kotaemon.storages.QdrantVectorStore",
        "kotaemon.embeddings.AzureOpenAIEmbeddings",
        "kotaemon.llms.AzureChatOpenAI",
        "kotaemon.agents.openai.OpenAIAgent",
    ],
)
def test_supported_configurable_classpaths_remain_importable(classpath):
    module, _, name = classpath.rpartition(".")
    assert callable(getattr(importlib.import_module(module), name))


@pytest.mark.parametrize(
    "module",
    ["llama_index.agent.openai", "llama_index.multi_modal_llms.openai"],
)
def test_obsolete_third_party_import_paths_are_no_longer_shipped(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
