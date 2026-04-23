from kotaemon.base import Document, RetrievedDocument
from kotaemon.indices.qa.format_context import (
    EVIDENCE_MODE_FIGURE,
    EVIDENCE_MODE_TABLE,
    EVIDENCE_MODE_TEXT,
    PrepareEvidencePipeline,
)


def _prepare(docs: list[RetrievedDocument]) -> tuple[int, str, list[str]]:
    pipeline = PrepareEvidencePipeline(trim_func=lambda texts: texts)
    return pipeline.run(docs).content


def test_image_type_preserves_origin_and_caption_ocr_alt_text():
    mode, evidence, images = _prepare(
        [
            RetrievedDocument(
                text="chart content",
                id_="image-doc",
                metadata={
                    "type": "image",
                    "file_name": "report.pdf",
                    "page_label": "3",
                    "image_origin": "data:image/png;base64,abc",
                    "caption": "Revenue by region",
                    "ocr_text": "North 42",
                },
            )
        ]
    )

    assert mode == EVIDENCE_MODE_FIGURE
    assert images == ["data:image/png;base64,abc"]
    assert "Figure from report.pdf (Page 3)" in evidence
    assert "Caption: Revenue by region" in evidence
    assert "OCR: North 42" in evidence
    assert "chart content" in evidence
    assert "alt='Caption: Revenue by region OCR: North 42 chart content'" in evidence


def test_figure_element_type_is_treated_as_figure():
    mode, evidence, images = _prepare(
        [
            RetrievedDocument(
                text="architecture diagram",
                id_="figure-doc",
                metadata={
                    "element_type": "figure",
                    "file_name": "design.pdf",
                    "image_origin": "figure-image",
                    "caption": "System layout",
                },
            )
        ]
    )

    assert mode == EVIDENCE_MODE_FIGURE
    assert images == ["figure-image"]
    assert "Figure from design.pdf" in evidence
    assert "Caption: System layout" in evidence


def test_formula_evidence_includes_formula_fields_and_location_metadata():
    mode, evidence, images = _prepare(
        [
            RetrievedDocument(
                text="fallback formula",
                id_="formula-doc",
                metadata={
                    "element_type": "formula",
                    "file_name": "math.pdf",
                    "page_label": "7",
                    "bbox": [10, 20, 30, 40],
                    "normalized_formula": "E = mc^2",
                    "raw_pdf_text": "E = m c 2",
                    "formula_kind": "display",
                },
            )
        ]
    )

    assert mode == EVIDENCE_MODE_TEXT
    assert images == []
    assert "Formula from math.pdf (Page 7)" in evidence
    assert "Normalized formula: E = mc^2" in evidence
    assert "Raw PDF text: E = m c 2" in evidence
    assert "Formula kind: display" in evidence
    assert "Page: 7" in evidence
    assert "Bbox: [10, 20, 30, 40]" in evidence


def test_text_and_table_evidence_keep_existing_behavior():
    mode, evidence, images = _prepare(
        [
            RetrievedDocument(
                text="plain\ntext",
                id_="text-doc",
                metadata={"type": "text", "file_name": "notes.txt"},
            ),
            RetrievedDocument(
                text="table fallback",
                id_="table-doc",
                metadata={
                    "type": "table",
                    "file_name": "table.pdf",
                    "table_origin": "<table><tr><td>A</td></tr></table>",
                },
            ),
        ]
    )

    assert mode == EVIDENCE_MODE_TABLE
    assert images == []
    assert "<br><b>Content from notes.txt: </b> plain text" in evidence
    assert "<br><b>Table from table.pdf</b>" in evidence
    assert "<table><tr><td>A</td></tr></table>" in evidence
