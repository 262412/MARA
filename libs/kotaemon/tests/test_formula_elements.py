from kotaemon.base import Document
from kotaemon.indices.formulas import (
    expand_documents_with_formula_elements,
    extract_formula_elements,
)


def test_extracts_inline_and_display_latex_formulas_with_metadata():
    doc = Document(
        text="Einstein wrote $E = mc^2$.\n\nThen:\n\\[ x_i = y_i + z_i \\]",
        metadata={
            "page": 3,
            "bbox": [10, 20, 30, 40],
            "file_id": "file-1",
            "document_id": "doc-1",
        },
    )

    formulas = extract_formula_elements(doc)

    assert [formula.text for formula in formulas] == [
        "E = mc^2",
        "x_i = y_i + z_i",
    ]
    assert [formula.metadata["formula_kind"] for formula in formulas] == [
        "inline",
        "display",
    ]
    assert all(formula.metadata["type"] == "formula" for formula in formulas)
    assert formulas[0].metadata["raw_pdf_text"] == "$E = mc^2$"
    assert formulas[0].metadata["normalized_formula"] == "E = mc^2"
    assert formulas[0].metadata["page"] == 3
    assert formulas[0].metadata["bbox"] == [10, 20, 30, 40]
    assert formulas[0].metadata["file_id"] == "file-1"
    assert formulas[0].metadata["document_id"] == "doc-1"


def test_extracts_multiple_display_and_inline_delimiter_styles():
    doc = Document(
        text="Use \\(a + b = c\\), $$F = ma$$, and \\[\\alpha_i = \\beta_i\\].",
        metadata={"page_number": 2},
    )

    formulas = extract_formula_elements(doc)

    assert [formula.text for formula in formulas] == [
        "a + b = c",
        "F = ma",
        "\\alpha_i = \\beta_i",
    ]
    assert [formula.metadata["formula_kind"] for formula in formulas] == [
        "inline",
        "display",
        "display",
    ]


def test_extracts_equation_like_text_without_delimiters():
    doc = Document(
        text="The relationship is E = mc^2. Another row: x_i = y_i + z_i.",
        metadata={"source_id": "paper-a"},
    )

    formulas = extract_formula_elements(doc)

    assert [formula.text for formula in formulas] == [
        "E = mc^2",
        "x_i = y_i + z_i",
    ]
    assert all(formula.metadata["formula_kind"] == "inline" for formula in formulas)
    assert formulas[0].metadata["raw_pdf_text"] == "E = mc^2"
    assert formulas[0].metadata["source_id"] == "paper-a"


def test_avoids_plain_short_text_and_assignment_like_phrases():
    docs = [
        Document(text="Plain short text.", metadata={}),
        Document(text="Status = approved", metadata={}),
        Document(text="Title = Introduction", metadata={}),
        Document(text="$5 and $10 are prices, not formulas.", metadata={}),
    ]

    for doc in docs:
        assert extract_formula_elements(doc) == []


def test_formula_image_metadata_is_preserved_or_mapped_from_image_origin():
    direct = Document(
        text="$x = y$",
        metadata={"formula_image": "formula.png", "page": 1},
    )
    mapped = Document(
        text="$a = b$",
        metadata={"image_origin": {"path": "crop.png"}, "page": 2},
    )

    direct_formula = extract_formula_elements(direct)[0]
    mapped_formula = extract_formula_elements(mapped)[0]

    assert direct_formula.metadata["formula_image"] == "formula.png"
    assert mapped_formula.metadata["formula_image"] == {"path": "crop.png"}
    assert mapped_formula.metadata["image_origin"] == {"path": "crop.png"}


def test_expand_documents_appends_formula_elements_after_original_documents():
    doc = Document(text="Mass energy: $E = mc^2$.", metadata={"document_id": "doc-1"})
    plain = Document(text="No formula here.", metadata={"document_id": "doc-2"})

    expanded = expand_documents_with_formula_elements([doc, plain])

    assert expanded[:2] == [doc, plain]
    assert len(expanded) == 3
    assert expanded[2].text == "E = mc^2"
    assert expanded[2].metadata["type"] == "formula"
