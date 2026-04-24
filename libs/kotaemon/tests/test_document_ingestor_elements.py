from kotaemon.base import Document
from kotaemon.indices.extractors import BaseDocParser
from kotaemon.indices.ingests import DocumentIngestor
from kotaemon.indices.splitters import BaseSplitter


class StubReader:
    def __init__(self, documents):
        self.documents = documents

    def __call__(self):
        return self.documents


class CapturingSplitter(BaseSplitter):
    def __init__(self, chunks):
        super().__init__()
        self._chunks = chunks
        self._received_documents = None

    def run(self, documents):
        self._received_documents = documents
        return self._chunks

    @property
    def received_documents(self):
        return self._received_documents


class CapturingParser(BaseDocParser):
    def __init__(self):
        super().__init__()
        self._received_nodes = None

    def run(self, nodes):
        self._received_nodes = nodes
        for node in nodes:
            node.metadata["parsed_by"] = "custom-parser"
        return nodes

    @property
    def received_nodes(self):
        return self._received_nodes


def test_run_normalizes_reader_documents_before_split_and_restores_chunk_metadata(
    monkeypatch,
):
    raw_table = Document(
        text="Revenue table before split",
        metadata={
            "type": "table",
            "source": "deck-1",
            "page_label": "7",
            "bbox": [0, 1, 2, 3],
            "table_origin": "| Revenue |",
        },
    )
    chunk = Document(
        text="Revenue table chunk",
        metadata={
            "element_id": "legacy-copied-parent-id",
        },
    )
    splitter = CapturingSplitter([chunk])
    ingestor = DocumentIngestor(text_splitter=splitter)
    monkeypatch.setattr(
        ingestor,
        "_get_reader",
        lambda input_files: StubReader([raw_table]),
    )

    nodes = ingestor.run("fake.pdf")

    normalized_raw = splitter.received_documents[0]
    raw_metadata = normalized_raw.metadata
    assert raw_metadata["element_id"]
    assert raw_metadata["element_type"] == "table"
    assert raw_metadata["source_id"] == "deck-1"
    assert raw_metadata["page_number"] == 7
    assert raw_metadata["page_label"] == "7"
    assert raw_metadata["bbox"] == "[0.0,1.0,2.0,3.0]"

    node_metadata = nodes[0].metadata
    assert node_metadata["parent_element_id"] == raw_metadata["element_id"]
    assert node_metadata["element_id"] != raw_metadata["element_id"]
    assert node_metadata["element_type"] == "table"
    assert node_metadata["source_id"] == "deck-1"
    assert node_metadata["page_number"] == 7
    assert node_metadata["page_label"] == "7"
    assert node_metadata["table_origin"] == "| Revenue |"


def test_run_invokes_custom_doc_parsers_after_splitter_with_normalized_chunks(
    monkeypatch,
):
    raw_figure = Document(
        text="Chart on the page",
        metadata={
            "type": "image",
            "doc_id": "report-1",
            "page": "3",
            "image_origin": "chart.png",
        },
    )
    chunk = Document(text="Chart chunk", metadata={})
    splitter = CapturingSplitter([chunk])
    parser = CapturingParser()
    ingestor = DocumentIngestor(text_splitter=splitter, doc_parsers=[parser])
    monkeypatch.setattr(
        ingestor,
        "_get_reader",
        lambda input_files: StubReader([raw_figure]),
    )

    nodes = ingestor.run("fake.pdf")

    parser_metadata = parser.received_nodes[0].metadata
    raw_metadata = splitter.received_documents[0].metadata
    assert parser_metadata["parent_element_id"] == raw_metadata["element_id"]
    assert parser_metadata["element_type"] == "figure"
    assert parser_metadata["source_id"] == "report-1"
    assert parser_metadata["page_number"] == 3
    assert parser_metadata["page_label"] == "3"
    assert nodes[0].metadata["parsed_by"] == "custom-parser"
