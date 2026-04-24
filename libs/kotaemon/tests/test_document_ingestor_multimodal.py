from kotaemon.base import Document
from kotaemon.indices.ingests import DocumentIngestor
from kotaemon.indices.splitters import BaseSplitter


class StubReader:
    def __init__(self, documents):
        self.documents = documents

    def __call__(self):
        return self.documents


class CapturingSplitter(BaseSplitter):
    def __init__(self):
        super().__init__()
        self._received_documents = None

    def run(self, documents):
        self._received_documents = documents
        return documents

    @property
    def received_documents(self):
        return self._received_documents


def test_run_expands_detected_formulas_before_split(monkeypatch):
    raw_page = Document(
        text="The objective is $$ L = \\sum_i x_i^2 $$ and the update is x_i = y_i + z_i.",
        metadata={
            "source": "paper-1",
            "page_label": "5",
            "file_name": "paper.pdf",
        },
    )
    splitter = CapturingSplitter()
    ingestor = DocumentIngestor(text_splitter=splitter)
    monkeypatch.setattr(
        ingestor, "_get_reader", lambda input_files: StubReader([raw_page])
    )

    nodes = ingestor.run("fake.pdf")

    formula_docs = [
        document
        for document in splitter.received_documents
        if document.metadata.get("element_type") == "formula"
    ]
    assert len(formula_docs) == 2
    assert {doc.metadata["formula_kind"] for doc in formula_docs} == {
        "display",
        "inline",
    }
    assert all(doc.metadata["source_id"] == "paper-1" for doc in formula_docs)
    assert all(doc.metadata["page_number"] == 5 for doc in formula_docs)
    assert any("L = \\sum_i x_i^2" in doc.text for doc in formula_docs)
    assert any("x_i = y_i + z_i" in doc.text for doc in formula_docs)

    formula_nodes = [
        document
        for document in nodes
        if document.metadata.get("element_type") == "formula"
    ]
    assert formula_nodes


def test_run_preserves_figure_caption_ocr_and_image_metadata(monkeypatch):
    raw_figure = Document(
        text="",
        metadata={
            "type": "image",
            "source": "paper-1",
            "page_label": "2",
            "file_name": "paper.pdf",
            "caption": "Figure 1. Training pipeline",
            "ocr_text": "encoder decoder",
            "image_origin": "data:image/png;base64,abc",
            "bbox": [0.1, 0.2, 0.8, 0.9],
        },
    )
    splitter = CapturingSplitter()
    ingestor = DocumentIngestor(text_splitter=splitter)
    monkeypatch.setattr(
        ingestor, "_get_reader", lambda input_files: StubReader([raw_figure])
    )

    nodes = ingestor.run("fake.pdf")

    figure_docs = [
        document
        for document in splitter.received_documents
        if document.metadata.get("element_type") == "figure"
    ]
    assert figure_docs
    figure = figure_docs[0]
    assert figure.text == "Figure 1. Training pipeline\nencoder decoder"
    assert figure.metadata["caption"] == "Figure 1. Training pipeline"
    assert figure.metadata["ocr_text"] == "encoder decoder"
    assert figure.metadata["image_origin"] == "data:image/png;base64,abc"
    assert figure.metadata["bbox"] == "[0.1,0.2,0.8,0.9]"

    node = next(
        document
        for document in nodes
        if document.metadata.get("element_type") == "figure"
    )
    assert node.metadata["caption"] == "Figure 1. Training pipeline"
    assert node.metadata["ocr_text"] == "encoder decoder"
    assert node.metadata["image_origin"] == "data:image/png;base64,abc"
