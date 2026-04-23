from kotaemon.base import Document
from kotaemon.indices.elements import document_to_element, normalize_formula_text


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

    assert document_to_element(first).element_id == document_to_element(second).element_id
