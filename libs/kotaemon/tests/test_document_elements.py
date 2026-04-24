import json

from kotaemon.base import Document
from kotaemon.indices.elements import (
    annotate_document_with_element_metadata,
    document_to_element,
    normalize_formula_text,
)


def test_text_document_becomes_text_element_with_normalized_page():
    doc = Document(
        text="Plain text",
        metadata={
            "source": "source-1",
            "file_name": "paper.pdf",
            "page_label": "03",
            "parser": "unit-parser",
        },
    )

    element = document_to_element(doc)

    assert element.element_type == "text"
    assert element.text == "Plain text"
    assert element.page_label == "03"
    assert element.page_number == 3
    assert element.source_id == "source-1"
    assert element.file_name == "paper.pdf"
    assert element.parser == "unit-parser"
    assert element.metadata["page_label"] == "03"


def test_metadata_type_maps_to_supported_element_types():
    cases = [
        ("image", "figure"),
        ("thumbnail", "thumbnail"),
        ("table", "table"),
        ("formula", "formula"),
        ("page", "page"),
    ]

    for metadata_type, element_type in cases:
        doc = Document(
            text="content",
            metadata={
                "type": metadata_type,
                "page_number": "2",
                "bbox": [1, 2, 3, 4],
                "confidence": "0.95",
                "image_origin": "data:image/png;base64,abc",
            },
        )

        element = document_to_element(doc)

        assert element.element_type == element_type
        assert element.page_number == 2
        assert element.bbox == (1.0, 2.0, 3.0, 4.0)
        assert element.confidence == 0.95
        assert element.image_origin == "data:image/png;base64,abc"


def test_formula_text_normalization_preserves_math_and_collapses_whitespace():
    assert (
        normalize_formula_text("  E   =  m c ^ 2 \n + \\frac{ a }{ b }  ")
        == "E = m c ^ 2 + \\frac{ a }{ b }"
    )

    doc = Document(
        text="  x _ { n + 1 }   =   x_n + \\alpha  ",
        metadata={"type": "formula", "formula_format": "latex"},
    )

    element = document_to_element(doc)

    assert element.text == "x _ { n + 1 } = x_n + \\alpha"
    assert element.formula == {
        "text": "x _ { n + 1 } = x_n + \\alpha",
        "format": "latex",
    }


def test_element_id_is_stable_for_same_source_page_type_text_and_bbox():
    first = Document(
        text="same text",
        metadata={
            "source_id": "source-1",
            "page_number": 1,
            "type": "table",
            "bbox": [0, 1, 2, 3],
            "confidence": 0.5,
        },
    )
    second = Document(
        text="same text",
        metadata={
            "source_id": "source-1",
            "page_number": "1",
            "type": "table",
            "bbox": ["0", "1", "2", "3"],
            "confidence": 0.9,
        },
    )

    assert (
        document_to_element(first).element_id == document_to_element(second).element_id
    )


def test_document_to_element_normalizes_structure_aliases():
    doc = Document(
        text="table body",
        metadata={
            "element_id": "element-1",
            "type": "annotation",
            "parent_id": "parent-1",
            "neighbors": ["prev-1", 42, ""],
            "caption": "Table 1",
            "text_as_html": "<table><tr><td>A</td></tr></table>",
            "raw_pdf_text": "raw table text",
            "layout_blocks": [{"type": "table", "bbox": [0, 1, 2, 3]}],
        },
    )

    element = document_to_element(doc)

    assert element.element_type == "annotation"
    assert element.parent_element_id == "parent-1"
    assert element.neighbor_element_ids == ("prev-1", "42")
    assert element.caption == "Table 1"
    assert element.table == "<table><tr><td>A</td></tr></table>"
    assert element.raw_pdf_text == "raw table text"
    assert element.layout_blocks == [{"type": "table", "bbox": [0, 1, 2, 3]}]


def test_document_to_element_normalizes_table_figure_formula_and_page_aliases():
    table_doc = Document(
        text="table",
        metadata={"type": "table", "table_origin": "| A |"},
    )
    figure_doc = Document(
        text="figure",
        metadata={"type": "figure", "image_text": "detected text"},
    )
    formula_doc = Document(
        text="fallback",
        metadata={
            "type": "formula",
            "latex": "  a   +   b  ",
            "image_origin": {"page": 1, "bbox": [1, 2, 3, 4]},
        },
    )
    page_doc = Document(
        text="page",
        metadata={"type": "page", "layout_blocks": [{"type": "text"}]},
    )

    assert document_to_element(table_doc).table == "| A |"
    assert document_to_element(figure_doc).ocr_text == "detected text"

    formula = document_to_element(formula_doc)
    assert formula.text == "a + b"
    assert formula.normalized_formula == "a + b"
    assert formula.formula_image == {"page": 1, "bbox": [1, 2, 3, 4]}

    assert document_to_element(page_doc).layout_blocks == [{"type": "text"}]


def test_annotate_document_metadata_is_vector_store_compatible_for_complex_fields():
    doc = Document(
        text="table",
        metadata={
            "type": "table",
            "bbox": {"x0": 0, "y0": 1, "x1": 2, "y1": 3},
            "parent_element_id": "parent-1",
            "neighbor_element_ids": ["prev-1", "next-1"],
            "caption": "Table 1",
            "table": {"cells": [["A"]]},
            "layout_blocks": [{"type": "table"}],
        },
    )

    annotate_document_with_element_metadata(doc)

    assert doc.metadata["element_type"] == "table"
    assert doc.metadata["bbox"] == "[0.0,1.0,2.0,3.0]"
    assert doc.metadata["neighbor_element_ids_json"] == '["prev-1","next-1"]'
    assert doc.metadata["table_json"] == '{"cells":[["A"]]}'
    assert doc.metadata["layout_blocks_json"] == '[{"type":"table"}]'
    assert "neighbor_element_ids" not in doc.metadata
    assert "table" not in doc.metadata
    assert "layout_blocks" not in doc.metadata
    assert all(
        value is None or isinstance(value, (str, int, float))
        for value in doc.metadata.values()
    )
    assert json.loads(doc.metadata["table_json"]) == {"cells": [["A"]]}


def test_neighbor_mapping_normalizes_to_neighbor_element_id_values():
    doc = Document(
        text="middle",
        metadata={
            "neighbor_element_ids": {
                "previous": "prev-id",
                "next": "next-id",
            }
        },
    )

    element = document_to_element(doc)
    annotate_document_with_element_metadata(doc)

    assert element.neighbor_element_ids == ("prev-id", "next-id")
    assert doc.metadata["neighbor_element_ids_json"] == '["prev-id","next-id"]'


def test_formula_annotation_sets_content_to_normalized_formula_and_flat_metadata():
    doc = Document(
        text="untrusted fallback",
        metadata={
            "type": "formula",
            "formula_text": "  x   =   y  ",
            "formula": {"source": "latex"},
            "formula_image": {"path": "formula.png"},
        },
    )

    annotate_document_with_element_metadata(doc)

    assert doc.text == "x = y"
    assert doc.content == "x = y"
    assert doc.metadata["formula_text"] == "x = y"
    assert doc.metadata["normalized_formula"] == "x = y"
    assert doc.metadata["formula_json"] == '{"source":"latex"}'
    assert doc.metadata["formula_image_json"] == '{"path":"formula.png"}'
    assert "formula" not in doc.metadata
    assert "formula_image" not in doc.metadata
    assert all(
        value is None or isinstance(value, (str, int, float))
        for value in doc.metadata.values()
    )
