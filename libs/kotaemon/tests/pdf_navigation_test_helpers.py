"""Synthetic PDFs and real parser/cache/index/preview observations."""

import base64
import json
from io import BytesIO
from unittest.mock import patch

import fitz
from PIL import Image
from pypdf import PdfReader

from kotaemon.embeddings import AzureOpenAIEmbeddings
from kotaemon.indices import VectorIndexing
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.qa.citation_refs import citation_target_from_document
from kotaemon.loaders import AutoReader, PDFThumbnailReader
from kotaemon.storages import SimpleFileDocumentStore, SimpleFileVectorStore

from .test_pdf_reading_contracts import PAGE_COLORS, _embedding_response

LABEL_CASES = {
    "duplicate": [
        {"startpage": 0, "style": "D", "firstpagenum": 7},
        {"startpage": 2, "style": "D", "firstpagenum": 7},
    ],
    "alphabetic": [{"startpage": 0, "style": "A", "firstpagenum": 27}],
    "roman_prefix": [{"startpage": 0, "style": "r", "prefix": "App-"}],
    "restart": [
        {"startpage": 0, "style": "D", "prefix": "Part-", "firstpagenum": 12},
        {"startpage": 2, "style": "D", "prefix": "Part-", "firstpagenum": 1},
    ],
}


def make_pdf(path, case):
    texts = ["Physical first", "", "Physical third"]
    with fitz.open() as pdf:
        for text, color in zip(texts, PAGE_COLORS):
            page = pdf.new_page(width=216, height=144)
            page.draw_rect(page.rect, color=color, fill=color)
            if text:
                page.insert_text((20, 60), text, color=(0, 0, 0))
        pdf.set_page_labels(LABEL_CASES[case])
        pdf.save(path)
    return path


def reader_for(route, full=False):
    reader = AutoReader("PDFReader") if route == "auto" else PDFThumbnailReader()
    if full:
        assert isinstance(reader, AutoReader)
        reader._reader.return_full_document = True
    return reader


def persisted_chain(root, path, documents):
    from ktem.index.file.deterministic_chunks import prepare_chunks_for_indexing
    from ktem.index.file.index_materialization import materialize_index_chunks

    chunks = materialize_index_chunks(
        documents,
        namespace="synthetic-source-table",
        file_id="source-A",
        file_name=path.name,
        splitter=None,
        deterministic_chunk_ids=False,
        prepare_chunks=prepare_chunks_for_indexing,
    )
    embedding = AzureOpenAIEmbeddings(
        azure_deployment="synthetic",
        azure_endpoint="https://example.invalid/",
        api_key="synthetic-key",
        api_version="synthetic",
    )
    pipeline = VectorIndexing(
        vector_store=SimpleFileVectorStore(root / "vectors"),
        doc_store=SimpleFileDocumentStore(root / "documents"),
        embedding=embedding,
        cache_dir=str(root / "chunks"),
        embedding_cache_dir=str(root / "embeddings"),
        index_contract="physical-page-v1",
    )
    with patch(
        "openai.resources.embeddings.Embeddings.create", side_effect=_embedding_response
    ):
        pipeline(chunks)
    ids = [document.doc_id for document in chunks]
    reloaded = SimpleFileDocumentStore(root / "documents").get(ids)
    vectors = SimpleFileVectorStore(root / "vectors")
    assert set(vectors.query([1.0, 0.0, 0.0], top_k=len(ids))[2]) == set(ids)
    return reloaded


def observe_chain(root, route, case):
    from ktem.utils.render import Render

    source = make_pdf(root / "fixture.pdf", case)
    reader = reader_for(route)
    extra = {
        "source_id": "source-A",
        "file_id": "source-A",
        "owner": "owner-A",
        "file_path": str(source),
        "file_type": "application/pdf",
    }
    first = load_data_with_parse_cache(
        reader, source, cache_dir=root / "cache", extra_info=extra
    )
    second = load_data_with_parse_cache(
        reader, source, cache_dir=root / "cache", extra_info=extra
    )
    assert not first.cache_hit and second.cache_hit
    assert [doc.doc_id for doc in first.documents] == [
        doc.doc_id for doc in second.documents
    ]
    reloaded = persisted_chain(root, source, second.documents)
    observations = []
    for document in reloaded:
        target = citation_target_from_document(document)
        try:
            preview = Render.preview("Evidence", document, highlight_text="Physical")
        except (ValueError, TypeError) as exc:
            preview = f"ERROR {type(exc).__name__}: {exc}"
        observations.append(
            {
                "target": target.to_dict(),
                "metadata": document.metadata,
                "text": document.text,
                "preview_html": preview,
            }
        )
    report = {
        "route": route,
        "case": case,
        "cache_key": first.cache_key,
        "miss_then_hit": True,
        "input_labels": PdfReader(source).page_labels,
        "parsed_metadata": [doc.metadata for doc in first.documents],
        "persisted": observations,
    }
    (root / "chain-observations.json").write_text(
        json.dumps(report, indent=2), encoding="utf8"
    )
    return source, reloaded, report


def thumbnail_pixel(document):
    with Image.open(
        BytesIO(base64.b64decode(document.metadata["image_origin"].split(",", 1)[1]))
    ) as image:
        return image.getpixel((5, 5))


def persisted_thumbnail_controller(root, documents, monkeypatch):
    from types import SimpleNamespace

    from ktem.pages.chat import page_preview
    from sqlmodel import Field, Session, SQLModel, create_engine

    class NavigationIndex(SQLModel, table=True):
        __tablename__ = "physical_navigation_contract"
        id: int | None = Field(default=None, primary_key=True)
        source_id: str
        target_id: str
        relation_type: str

    engine = create_engine(f"sqlite:///{root / 'navigation.sqlite'}")
    table = SQLModel.metadata.tables["physical_navigation_contract"]
    SQLModel.metadata.create_all(engine, tables=[table])
    with Session(engine) as session:
        session.add_all(
            [
                NavigationIndex(
                    source_id="source-A", target_id=doc.doc_id, relation_type="document"
                )
                for doc in documents
            ]
        )
        session.commit()
    monkeypatch.setattr(page_preview, "engine", engine)
    controller = page_preview.ChatPagePreviewController.__new__(
        page_preview.ChatPagePreviewController
    )
    controller._page_thumbnail_cache = {}
    index = SimpleNamespace(
        _resources={
            "Index": NavigationIndex,
            "DocStore": SimpleFileDocumentStore(root / "documents"),
        }
    )
    controller._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[index]))
    return controller, engine, table
