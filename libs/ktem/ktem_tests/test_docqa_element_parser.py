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


def test_element_index_records_infer_plain_text_financial_table():
    docs = [
        RetrievedDocument(
            text=(
                "Table of Contents\n"
                "ITEM 6. Selected Financial Data (In millions)\n"
                "2021 2020 2019\n"
                "Net sales $ 67,044 $ 65,398 $ 59,812\n"
                "Total current assets 19,815 19,378 17,095\n"
                "Total current liabilities 13,997 13,933 13,972\n"
            ),
            id_="finance-page-30",
            metadata={
                "file_id": "file-1",
                "file_name": "annual-report.pdf",
                "page_label": "30",
                "type": "image",
            },
        )
    ]

    records = element_records_from_documents(docs)

    assert len(records) == 1
    assert records[0]["modality"] == "table"
    assert records[0]["element_id"] == "table-finance-page-30"
    assert records[0]["page_label"] == "30"


def test_inferred_financial_elements_split_page_into_real_table_blocks():
    docs = [
        RetrievedDocument(
            text=(
                "CONSOLIDATED STATEMENTS OF INCOME (in millions)\n"
                "2022 2021\n"
                "Net sales 100 90\n"
                "Cost of products sold 60 55\n"
                "Management discussion between tables must not become a table row.\n"
                "CONSOLIDATED BALANCE SHEETS (in millions)\n"
                "2022 2021\n"
                "Inventories 30 25\n"
                "Total current assets 80 70\n"
            ),
            id_="mixed-finance-page",
            metadata={
                "file_id": "file-1",
                "file_name": "annual-report.pdf",
                "page_label": "41",
                "type": "image",
            },
        )
    ]

    records = element_records_from_documents(docs)

    assert len(records) == 2
    assert records[0]["element_id"] != records[1]["element_id"]
    assert "Inventories" not in records[0]["text"]
    assert "Net sales" not in records[1]["text"]
    assert records[0]["metadata"]["statement_kind"] == "income_statement"
    assert records[1]["metadata"]["statement_kind"] == "balance_sheet"
    assert all(
        record["metadata"]["financial_scope"] == "consolidated" for record in records
    )


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
