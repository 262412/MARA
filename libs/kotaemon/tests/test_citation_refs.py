from kotaemon.base import Document
from kotaemon.indices.qa.citation_refs import (
    CitationTarget,
    citation_target_from_document,
    citation_targets_from_spans,
)


def test_basic_text_target_uses_document_and_metadata_fields():
    doc = Document(
        text="A paragraph about phase six.",
        id_="doc-1",
        metadata={
            "source_id": "source-1",
            "file_name": "paper.pdf",
            "page_number": "2",
            "page_label": "ii",
        },
    )

    target = citation_target_from_document(doc)

    assert isinstance(target, CitationTarget)
    assert target.to_dict() == {
        "doc_id": "doc-1",
        "source_id": "source-1",
        "file_name": "paper.pdf",
        "page_number": 2,
        "page_label": "ii",
        "bbox": None,
        "element_id": None,
        "parent_element_id": None,
        "element_type": "text",
        "span_start": None,
        "span_end": None,
        "highlight_text": None,
    }


def test_formula_target_preserves_element_identity_and_bbox():
    doc = Document(
        text="E = mc^2",
        id_="formula-doc",
        metadata={
            "source": "equations.pdf",
            "filename": "equations.pdf",
            "page": "3",
            "bbox": [1, "2.5", 3, 4],
            "element_id": "formula-1",
            "parent_element_id": "page-3",
            "type": "formula",
        },
    )

    target = citation_target_from_document(doc)

    assert target.doc_id == "formula-doc"
    assert target.source_id == "equations.pdf"
    assert target.file_name == "equations.pdf"
    assert target.page_number == 3
    assert target.bbox == (1.0, 2.5, 3.0, 4.0)
    assert target.element_id == "formula-1"
    assert target.parent_element_id == "page-3"
    assert target.element_type == "formula"


def test_figure_target_uses_element_type_alias():
    doc = Document(
        text="A chart image",
        id_="figure-doc",
        metadata={
            "type": "image",
            "element_id": "fig-1",
            "bbox": (10, 20, 30, 40),
        },
    )

    target = citation_target_from_document(doc)

    assert target.element_type == "figure"
    assert target.element_id == "fig-1"
    assert target.bbox == (10.0, 20.0, 30.0, 40.0)


def test_span_target_includes_highlight_text_and_offsets():
    doc = Document(text="Alpha beta gamma", id_="doc-1")

    target = citation_target_from_document(doc, {"start": 6, "end": 10, "idx": 7})

    assert target.span_start == 6
    assert target.span_end == 10
    assert target.highlight_text == "beta"


def test_bbox_string_values_are_normalized():
    json_doc = Document(
        text="json bbox",
        id_="json-doc",
        metadata={"bbox": '[1, "2", 3.5, 4]'},
    )
    comma_doc = Document(
        text="comma bbox",
        id_="comma-doc",
        metadata={"bbox": "5, 6.25, 7, 8"},
    )

    assert citation_target_from_document(json_doc).bbox == (1.0, 2.0, 3.5, 4.0)
    assert citation_target_from_document(comma_doc).bbox == (5.0, 6.25, 7.0, 8.0)


def test_targets_from_spans_ignores_unknown_doc_ids():
    doc = Document(text="Alpha beta gamma", id_="known")
    spans = {
        "known": [{"start": 0, "end": 5}],
        "missing": [{"start": 0, "end": 7}],
    }

    targets = citation_targets_from_spans(spans, [doc])

    assert len(targets) == 1
    assert targets[0].doc_id == "known"
    assert targets[0].highlight_text == "Alpha"
