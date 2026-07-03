import json

from ktem.docqa.offline_layout_index import offline_element_records_for_file

from benchmark.ocr_layout_sidecars import (
    build_pdf_ocr_layout_sidecar,
    sidecar_path_for_pdf,
    write_pdf_ocr_layout_sidecar,
)


class _FakePage:
    def __init__(self, blocks):
        self._blocks = blocks

    def get_text(self, mode, sort=False):
        assert mode == "blocks"
        assert sort is True
        return self._blocks


class _FakeDocument:
    def __init__(self, pages):
        self._pages = pages
        self.closed = False

    def __len__(self):
        return len(self._pages)

    def load_page(self, index):
        return self._pages[index]

    def close(self):
        self.closed = True


class _FakeFitz:
    def __init__(self, document):
        self.document = document

    def open(self, _path):
        return self.document


def test_build_pdf_ocr_layout_sidecar_extracts_text_and_table_blocks(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF")
    document = _FakeDocument(
        [
            _FakePage(
                [
                    (
                        10,
                        20,
                        100,
                        120,
                        "Segment 2019 2020\nNorth 10 12\nSouth 8 9",
                    ),
                    (12, 130, 100, 160, "A short paragraph."),
                ]
            )
        ]
    )

    sidecar = build_pdf_ocr_layout_sidecar(
        pdf_path,
        document_id="report",
        fitz_module=_FakeFitz(document),
    )

    assert document.closed is True
    assert sidecar["parser_backend"] == "pymupdf_text_blocks"
    assert sidecar["source_document_id"] == "report"
    assert sidecar["layout_elements"][0]["type"] == "table"
    assert sidecar["layout_elements"][0]["element_type"] == "table"
    assert sidecar["layout_elements"][0]["element_id_aliases"] == [
        "table1",
        "text1",
        "image1",
    ]
    assert sidecar["layout_elements"][0]["element_type_aliases"] == [
        "table",
        "figure",
        "image",
    ]
    assert sidecar["layout_elements"][0]["page_label"] == "1"
    assert sidecar["layout_elements"][0]["bbox"] == [10.0, 20.0, 100.0, 120.0]
    assert sidecar["layout_elements"][1]["type"] == "text"


def test_write_pdf_ocr_layout_sidecar_uses_external_sidecar_name(tmp_path):
    pdf_path = tmp_path / "pdfs" / "report.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF")
    output_dir = tmp_path / "sidecars"
    document = _FakeDocument([_FakePage([(0, 0, 10, 10, "Revenue 42")])])

    written = write_pdf_ocr_layout_sidecar(
        pdf_path,
        output_dir,
        fitz_module=_FakeFitz(document),
    )

    assert written == sidecar_path_for_pdf(pdf_path, output_dir)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["source_file_name"] == "report.pdf"


def test_written_sidecar_loads_through_external_offline_layout_root(tmp_path):
    pdf_path = tmp_path / "pdfs" / "report.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF")
    output_dir = tmp_path / "sidecars"
    document = _FakeDocument(
        [_FakePage([(0, 0, 10, 10, "Segment 2019 2020\nNorth 10 12")])]
    )
    write_pdf_ocr_layout_sidecar(
        pdf_path,
        output_dir,
        fitz_module=_FakeFitz(document),
    )

    records = offline_element_records_for_file(
        file_id="file-1",
        file_name="report.pdf",
        file_path=pdf_path,
        sidecar_roots=[output_dir],
    )

    assert len(records) == 1
    assert records[0]["modality"] == "table"
    assert records[0]["element_id_aliases"] == ["table1", "text1", "image1"]
    assert records[0]["element_type_aliases"] == ["table", "figure", "image"]
    assert records[0]["metadata"]["index_source"] == "offline_layout_sidecar"
