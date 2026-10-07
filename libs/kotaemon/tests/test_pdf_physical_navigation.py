"""No test adds page_number after the reader: exercise the real production chain."""

import json
from urllib.parse import urlsplit

import pytest
from pypdf import PdfReader

from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.qa.citation_refs import citation_target_from_document

from .pdf_navigation_test_helpers import (
    LABEL_CASES,
    make_pdf,
    observe_chain,
    persisted_chain,
    persisted_thumbnail_controller,
    reader_for,
    thumbnail_pixel,
)
from .test_pdf_reading_contracts import PAGE_COLORS


@pytest.mark.parametrize("route", ["auto", "thumbnail"])
@pytest.mark.parametrize("case", list(LABEL_CASES))
def test_real_pdf_cache_index_reload_and_preview_keep_physical_pages(
    tmp_path, monkeypatch, route, case
):
    from ktem.pages.chat import page_preview_runtime

    source, reloaded, report = observe_chain(tmp_path, route, case)
    labels = PdfReader(source).page_labels
    text_docs = [doc for doc in reloaded if doc.metadata.get("type") != "thumbnail"]
    assert len(text_docs) == 3  # the physical blank page must not be dropped
    assert [item.get("page_number") for item in report["parsed_metadata"][:3]] == [
        1,
        2,
        3,
    ]
    assert [doc.metadata["page_label"] for doc in text_docs] == labels
    viewer = tmp_path / "pdfjs/web/viewer.html"
    viewer.parent.mkdir(parents=True)
    viewer.write_text("synthetic viewer asset", encoding="utf8")
    monkeypatch.setattr(
        page_preview_runtime, "get_pdfjs_runtime_dir", lambda _: viewer.parent.parent
    )
    targets = []
    for physical_page, document in enumerate(text_docs, 1):
        target = citation_target_from_document(document)
        assert target.page_number == physical_page
        assert target.source_id == "source-A" and target.doc_id == document.doc_id
        assert target.element_id == document.metadata["element_id"]
        assert target.page_label == labels[physical_page - 1]
        assert (
            document.text.strip()
            == PdfReader(source).pages[physical_page - 1].extract_text().strip()
        )
        url = page_preview_runtime.build_pdfjs_viewer_src(
            str(source), target.page_number
        )
        assert urlsplit(url).fragment == f"page={physical_page}"
        observation = next(
            row
            for row in report["persisted"]
            if row["target"]["doc_id"] == document.doc_id
        )
        assert f'data-page="{physical_page}"' in observation["preview_html"]
        targets.append({"doc_id": target.doc_id, "page": physical_page, "url": url})
    if route == "thumbnail":
        thumbnails = {
            doc.doc_id: doc
            for doc in reloaded
            if doc.metadata.get("type") == "thumbnail"
        }
        assert len(thumbnails) == 3
        for physical_page, document in enumerate(text_docs, 1):
            thumbnail = thumbnails[document.metadata["thumbnail_doc_id"]]
            assert thumbnail.metadata["page_number"] == physical_page
            assert thumbnail.metadata["page_label"] == labels[physical_page - 1]
            assert thumbnail_pixel(thumbnail) == tuple(
                int(value * 255) for value in PAGE_COLORS[physical_page - 1]
            )
        controller, engine, table = persisted_thumbnail_controller(
            tmp_path, reloaded, monkeypatch
        )
        try:
            for physical_page, document in enumerate(text_docs, 1):
                expected = thumbnails[document.metadata["thumbnail_doc_id"]].metadata[
                    "image_origin"
                ]
                assert (
                    controller._get_page_thumbnail("source-A", physical_page)
                    == expected
                )
                assert (
                    controller._get_page_thumbnail("source-A", physical_page)
                    == expected
                )
        finally:
            engine.dispose()
            table.metadata.remove(table)
    (tmp_path / "verified-navigation.json").write_text(
        json.dumps(targets, indent=2), encoding="utf8"
    )


def test_full_document_mode_has_no_single_page_target(tmp_path):
    from ktem.utils.render import Render

    source = make_pdf(tmp_path / "full.pdf", "duplicate")
    reader = reader_for("auto", full=True)
    extra = {
        "source_id": "source-A",
        "file_path": str(source),
        "file_type": "application/pdf",
    }
    for expected_hit in (False, True):
        result = load_data_with_parse_cache(
            reader, source, cache_dir=tmp_path / "cache", extra_info=extra
        )
        assert result.cache_hit == expected_hit and len(result.documents) == 1
        assert citation_target_from_document(result.documents[0]).page_number is None
    (document,) = persisted_chain(tmp_path, source, result.documents)
    assert citation_target_from_document(document).page_number is None
    rendered = Render.preview("Evidence", document, highlight_text="Physical")
    assert 'class="pdf-link"' not in rendered
    assert "Page position unavailable" in rendered


@pytest.mark.parametrize("route", ["auto", "thumbnail"])
@pytest.mark.parametrize("key", ["page_number", "page", "page_idx", "page_label"])
def test_runtime_metadata_cannot_forge_parser_page_position(tmp_path, route, key):
    path = make_pdf(tmp_path / "position.pdf", "duplicate")
    with pytest.raises(ValueError, match="parser-owned"):
        load_data_with_parse_cache(
            reader_for(route), path, cache_dir=tmp_path / "cache", extra_info={key: 99}
        )
    assert not list((tmp_path / "cache").rglob("*.json"))
