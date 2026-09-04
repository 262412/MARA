from kotaemon.artifact_producers import _chunk_markdown
from kotaemon.base.schema import Document


def test_image_chunk_without_origin_preserves_text_without_raising():
    document = Document(
        "OCR-only figure content",
        metadata={
            "type": "image",
            "page_label": 8,
            "file_name": "report.pdf",
        },
    )

    markdown = _chunk_markdown(document)

    assert "Page label: 8" in markdown
    assert "OCR-only figure content" in markdown
    assert "Image origin:" not in markdown


def test_image_chunk_with_origin_renders_image_reference():
    document = Document(
        "Figure caption",
        metadata={
            "type": "image",
            "image_origin": "data:image/png;base64,abc",
        },
    )

    markdown = _chunk_markdown(document)

    assert 'Image origin: <p><img src="data:image/png;base64,abc"></p>' in markdown
