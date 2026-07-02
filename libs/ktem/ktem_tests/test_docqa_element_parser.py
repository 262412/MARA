import ktem.docqa.multimodal_index as multimodal_index_module
from ktem.docqa.multimodal_index import element_records_from_documents

from kotaemon.base import RetrievedDocument


def test_element_index_records_parse_declared_table_without_element_id():
    docs = [
        RetrievedDocument(
            text="Table: Regional revenue\nNorth 10\nSouth 12",
            id_="table-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_type": "table",
                "caption": "Regional revenue",
            },
        )
    ]

    records = element_records_from_documents(docs)

    assert records == [
        {
            "evidence_id": "element:file-1:4:table-table-doc",
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "element_id": "table-table-doc",
            "modality": "table",
            "bbox": None,
            "caption": "Regional revenue",
            "text": "Table: Regional revenue\nNorth 10\nSouth 12",
            "source_backrefs": ["file-1#page:4"],
            "metadata": {
                "element_schema_version": "1.0",
                "index_source": "docstore_document",
                "parser_backend": "local_element_parser_v1",
                "parser_source_doc_id": "table-doc",
            },
        }
    ]


def test_element_index_records_parse_formula_from_text_without_element_metadata():
    docs = [
        RetrievedDocument(
            text=r"Formula: w_{t+1}=w_t-\eta\nabla L",
            id_="formula-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "5",
            },
        )
    ]

    records = element_records_from_documents(docs)

    assert records[0]["evidence_id"] == "element:file-1:5:formula-formula-doc"
    assert records[0]["element_id"] == "formula-formula-doc"
    assert records[0]["modality"] == "formula"
    assert records[0]["metadata"]["parser_backend"] == "local_element_parser_v1"
    assert records[0]["metadata"]["element_schema_version"] == "1.0"


def test_element_index_documents_round_trip_records_for_persistence():
    docs = [
        RetrievedDocument(
            text="Table: Regional revenue\nNorth 10\nSouth 12",
            id_="table-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_type": "table",
                "caption": "Regional revenue",
            },
        )
    ]

    assert hasattr(multimodal_index_module, "element_index_documents_from_documents")
    assert hasattr(multimodal_index_module, "element_records_from_index_documents")

    persisted_docs = multimodal_index_module.element_index_documents_from_documents(
        "file-1",
        docs,
    )

    assert len(persisted_docs) == 1
    assert persisted_docs[0].metadata["type"] == "mara_element_index"
    assert persisted_docs[0].metadata["source_id"] == "file-1"
    assert persisted_docs[0].metadata["element_index_relation_type"] == (
        "element_index"
    )
    assert multimodal_index_module.element_records_from_index_documents(
        persisted_docs
    ) == [
        {
            "evidence_id": "element:file-1:4:table-table-doc",
            "file_id": "file-1",
            "source_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "page_number": 4,
            "element_id": "table-table-doc",
            "element_type": "table",
            "modality": "table",
            "bbox": None,
            "caption": "Regional revenue",
            "text": "Table: Regional revenue\nNorth 10\nSouth 12",
            "source_backrefs": ["file-1#page:4"],
            "metadata": {
                "element_schema_version": "1.0",
                "index_source": "docstore_document",
                "parser_backend": "local_element_parser_v1",
                "parser_source_doc_id": "table-doc",
            },
        }
    ]


def test_persisted_element_records_normalize_locator_aliases():
    persisted_docs = multimodal_index_module.element_index_documents_from_records(
        "file-1",
        [
            {
                "evidence_id": "element:file-1:64:image4",
                "source_id": "inditex_2021",
                "file_id": "file-1",
                "source_name": "inditex_2021.pdf",
                "page": 64,
                "element_id": "image4",
                "element_type": "table",
                "text": "Amortisation and depreciation charge",
            }
        ],
    )

    [record] = multimodal_index_module.element_records_from_index_documents(
        persisted_docs
    )

    assert record["source_id"] == "inditex_2021"
    assert record["page_label"] == "64"
    assert record["page_number"] == 64
    assert record["element_type"] == "table"
    assert record["modality"] == "table"
