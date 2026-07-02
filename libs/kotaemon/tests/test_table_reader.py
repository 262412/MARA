import json
from pathlib import Path

import pytest

from kotaemon.loaders import (
    MathpixPDFReader,
    OCRReader,
    PandasCSVReader,
    PandasExcelReader,
)

from .conftest import skip_when_unstructured_pdf_not_installed

input_file = Path(__file__).parent / "resources" / "table.pdf"
input_file_excel = Path(__file__).parent / "resources" / "dummy.xlsx"


@pytest.fixture
def fullocr_output():
    with open(
        Path(__file__).parent / "resources" / "fullocr_sample_output.json",
        encoding="utf-8",
    ) as f:
        fullocr = json.load(f)
    return fullocr


@pytest.fixture
def mathpix_output():
    with open(Path(__file__).parent / "resources" / "policy.md", encoding="utf-8") as f:
        content = f.read()
    return content


@skip_when_unstructured_pdf_not_installed
def test_ocr_reader(fullocr_output):
    reader = OCRReader()
    documents = reader.load_data(input_file, response_content=fullocr_output)
    table_docs = [doc for doc in documents if doc.metadata.get("type", "") == "table"]
    assert len(table_docs) == 2


def test_mathpix_reader(mathpix_output):
    reader = MathpixPDFReader()
    documents = reader.load_data(input_file, response_content=mathpix_output)
    table_docs = [doc for doc in documents if doc.metadata.get("type", "") == "table"]
    assert len(table_docs) == 4


def test_excel_reader():
    reader = PandasExcelReader()
    documents = reader.load_data(
        input_file_excel,
    )
    assert len(documents) == 1


def test_csv_reader_emits_row_and_column_search_text(tmp_path):
    input_file_csv = tmp_path / "format_smoke.csv"
    input_file_csv.write_text(
        "question,answer,status\n"
        "What is the CSV smoke answer?,CSV smoke answer,ready\n",
        encoding="utf-8",
    )

    reader = PandasCSVReader()
    documents = reader.load_data(input_file_csv)

    assert len(documents) == 1
    assert "row 1:" in documents[0].text
    assert "question: What is the CSV smoke answer?" in documents[0].text
    assert "answer: CSV smoke answer" in documents[0].text
    assert documents[0].metadata["type"] == "table"
    assert documents[0].metadata["sheet_name"] == "format_smoke"


def test_default_file_extractors_route_csv_to_csv_reader():
    from kotaemon.indices.ingests.files import KH_DEFAULT_FILE_EXTRACTORS

    assert isinstance(KH_DEFAULT_FILE_EXTRACTORS[".csv"], PandasCSVReader)
