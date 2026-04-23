from pathlib import Path
from unittest.mock import Mock

from PIL import Image

from kotaemon.loaders.azureai_document_intelligence_loader import (
    AzureAIDocumentIntelligenceLoader,
)
from kotaemon.loaders.docling_loader import DoclingReader


class _DoclingDocument:
    def __init__(self, payload):
        self._payload = payload

    def export_to_dict(self):
        return self._payload


class _DoclingConversion:
    def __init__(self, payload):
        self.document = _DoclingDocument(payload)


def test_docling_reader_keeps_figure_crop_and_caption_without_vlm(
    monkeypatch, tmp_path
):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    payload = {
        "pictures": [
            {
                "captions": [{"$ref": "#/texts/0"}],
                "prov": [
                    {
                        "page_no": 1,
                        "bbox": {
                            "l": 0.1,
                            "t": 0.2,
                            "r": 0.8,
                            "b": 0.9,
                            "coord_origin": "TOPLEFT",
                        },
                    }
                ],
            }
        ],
        "tables": [],
        "texts": [{"text": "Figure 1. Pipeline", "prov": [{"page_no": 1}]}],
        "pages": {"1": {"size": {"width": 100, "height": 100}}},
    }
    monkeypatch.setattr(
        "kotaemon.loaders.docling_loader.crop_image",
        lambda file_path, bbox, page_number: Image.new("RGB", (4, 4), color="white"),
    )
    caption_mock = Mock(return_value="generated caption")
    monkeypatch.setattr(
        "kotaemon.loaders.docling_loader.generate_single_figure_caption",
        caption_mock,
    )

    reader = DoclingReader()
    monkeypatch.setattr(
        reader,
        "_convert_file",
        lambda file_path: _DoclingConversion(payload),
    )
    reader.vlm_endpoint = ""

    documents = reader.load_data(pdf_path)

    figures = [doc for doc in documents if doc.metadata.get("type") == "image"]
    assert len(figures) == 1
    figure = figures[0]
    assert figure.text == "Figure 1. Pipeline"
    assert figure.metadata["caption"] == "Figure 1. Pipeline"
    assert figure.metadata["bbox"] == [0.1, 0.2, 0.8, 0.9]
    assert figure.metadata["image_origin"].startswith("data:image/png;base64,")
    caption_mock.assert_not_called()


class _AzurePage(dict):
    pass


class _AzureResult(dict):
    def __init__(self):
        super().__init__(
            figures=[
                {
                    "boundingRegions": [
                        {
                            "pageNumber": 1,
                            "polygon": [10, 20, 80, 20, 80, 90, 10, 90],
                        }
                    ],
                    "spans": [{"offset": 0, "length": 18}],
                    "caption": {"spans": [{"offset": 0, "length": 18}]},
                }
            ],
            tables=[],
        )
        self.content = "Figure 1. Pipeline\nBody text"
        self.pages = [_AzurePage(width=100, height=100)]


def test_azure_reader_keeps_figure_crop_and_caption_without_vlm(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        "kotaemon.loaders.azureai_document_intelligence_loader.crop_image",
        lambda file_path, bbox, page_number: Image.new("RGB", (4, 4), color="white"),
    )
    caption_mock = Mock(return_value="generated caption")
    monkeypatch.setattr(
        "kotaemon.loaders.azureai_document_intelligence_loader.generate_single_figure_caption",
        caption_mock,
    )

    reader = AzureAIDocumentIntelligenceLoader(endpoint="endpoint", credential="key")
    monkeypatch.setattr(reader, "_analyze_document", lambda file_path: _AzureResult())
    reader.vlm_endpoint = ""

    documents = reader.load_data(Path(pdf_path))

    figures = [doc for doc in documents if doc.metadata.get("type") == "image"]
    assert len(figures) == 1
    figure = figures[0]
    assert figure.text == "Figure 1. Pipeline"
    assert figure.metadata["caption"] == "Figure 1. Pipeline"
    assert figure.metadata["bbox"] == [0.1, 0.2, 0.8, 0.9]
    assert figure.metadata["image_origin"].startswith("data:image/png;base64,")
    caption_mock.assert_not_called()
