"""Display labels and physical positions are independent persisted contracts."""

import base64
import json
from copy import deepcopy
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image
from pypdf import PdfReader

from kotaemon.base import Document
from kotaemon.indices.qa.citation_refs import citation_target_from_document
from kotaemon.loaders import AutoReader
from kotaemon.loaders.pdf_loader import get_page_thumbnails

from .test_pdf_reading_contracts import PAGE_COLORS, PAGE_TEXT, write_pdf


def test_duplicate_labels_do_not_replace_physical_order_or_thumbnail_positions(
    tmp_path,
):
    source = write_pdf(
        tmp_path / "duplicates.pdf",
        [
            {"startpage": 0, "style": "D", "firstpagenum": 7},
            {"startpage": 2, "style": "D", "firstpagenum": 7},
        ],
    )
    assert PdfReader(source).page_labels == ["7", "8", "7"]
    documents = AutoReader("PDFReader").load_data(source)
    assert [document.text.strip() for document in documents] == PAGE_TEXT
    assert [document.metadata["page_label"] for document in documents] == [
        "7",
        "8",
        "7",
    ]
    images = get_page_thumbnails(source, [2, 0, 1])
    for image_data, index in zip(images, [2, 0, 1]):
        with Image.open(
            BytesIO(base64.b64decode(image_data.split(",", 1)[1]))
        ) as image:
            assert image.getpixel((5, 5)) == tuple(
                int(value * 255) for value in PAGE_COLORS[index]
            )
    assert citation_target_from_document(documents[0]).page_number == 1
    assert citation_target_from_document(documents[2]).page_number == 3
    # Historical label-only records still cannot establish a physical position.
    old = Document(text="saved text", metadata={"page_label": "7"})
    assert citation_target_from_document(old).page_number is None


def test_persisted_known_one_based_position_drives_preview_without_rewriting_label(
    tmp_path, monkeypatch
):
    from ktem.pages.chat import page_preview_runtime

    source = write_pdf(tmp_path / "history.pdf")
    old = Document(
        text="saved text",
        doc_id="old-doc",
        metadata={
            "source_id": "old-source",
            "file_name": source.name,
            "element_id": "old-element",
            "page_number": 2,
            "page_label": "AB",
        },
    )
    serialized = json.loads(json.dumps(old.to_dict()))
    restored = Document.from_dict(deepcopy(serialized))
    target = citation_target_from_document(restored)
    assert (target.doc_id, target.source_id, target.element_id) == (
        "old-doc",
        "old-source",
        "old-element",
    )
    assert target.page_number == 2 and target.page_label == "AB"
    assert restored.to_dict() == serialized
    viewer_root = tmp_path / "pdfjs"
    (viewer_root / "web").mkdir(parents=True)
    (viewer_root / "web/viewer.html").write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        page_preview_runtime, "get_pdfjs_runtime_dir", lambda _: viewer_root
    )
    url = page_preview_runtime.build_pdfjs_viewer_src(
        str(source), target.page_number, "pdf"
    )
    assert urlsplit(url).fragment == "page=2"
    assert (
        PdfReader(source).pages[target.page_number - 1].extract_text().strip()
        == PAGE_TEXT[1]
    )


def test_legacy_page_idx_is_a_raw_alias_without_an_inferred_base():
    document = Document(
        "old",
        metadata={"source_id": "source", "page_idx": 2, "page_label": "duplicate"},
    )
    target = citation_target_from_document(document)
    # Existing alias normalization does not establish whether page_idx is zero
    # or one based. Do not admit this as verified navigation without provenance.
    assert target.page_number == 2
    assert target.page_label == "duplicate"
