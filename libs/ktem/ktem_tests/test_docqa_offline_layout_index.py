import json
from types import SimpleNamespace

from ktem.docqa.offline_layout_index import (
    offline_element_records_for_documents,
    offline_element_records_for_file,
    offline_layout_sidecar_paths,
)


def test_offline_layout_sidecar_records_normalize_page_elements(tmp_path):
    source_path = tmp_path / "report.pdf"
    source_path.write_bytes(b"%PDF")
    sidecar_path = tmp_path / "report.pdf.mara-elements.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "parser": "docling",
                "pages": [
                    {
                        "page": 4,
                        "elements": [
                            {
                                "type": "table",
                                "caption": "Regional revenue",
                                "text": "North 10\nSouth 12",
                                "bbox": [10, 20, 30, 40],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records = offline_element_records_for_file(
        file_id="file-1",
        file_name="report.pdf",
        file_path=source_path,
    )

    assert records == [
        {
            "evidence_id": "element:file-1:4:table-4-1",
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "element_id": "table-4-1",
            "modality": "table",
            "bbox": [10, 20, 30, 40],
            "caption": "Regional revenue",
            "text": "North 10\nSouth 12",
            "source_backrefs": ["file-1#page:4"],
            "metadata": {
                "element_schema_version": "1.0",
                "sidecar_schema_version": "legacy",
                "index_source": "offline_layout_sidecar",
                "offline_layout_record_index": 0,
                "offline_layout_sidecar": "report.pdf.mara-elements.json",
                "parser_backend": "docling",
            },
        }
    ]


def test_offline_layout_records_for_documents_consumes_file_once(tmp_path):
    source_path = tmp_path / "report.pdf"
    source_path.write_bytes(b"%PDF")
    sidecar_path = tmp_path / "report.pdf.mara-elements.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "layout_elements": [
                    {
                        "page_label": "2",
                        "element_id": "figure-a",
                        "type": "figure",
                        "caption": "Architecture diagram",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    document = SimpleNamespace(
        metadata={
            "file_path": str(source_path),
            "file_name": "report.pdf",
        }
    )

    first_records = offline_element_records_for_documents(
        file_id="file-consume-once",
        documents=[document],
    )
    second_records = offline_element_records_for_documents(
        file_id="file-consume-once",
        documents=[document],
    )

    assert len(first_records) == 1
    assert second_records == []


def test_offline_layout_sidecar_paths_include_external_sidecar_root(tmp_path):
    source_path = tmp_path / "pdfs" / "report.pdf"
    source_path.parent.mkdir()
    source_path.write_bytes(b"%PDF")
    sidecar_root = tmp_path / "sidecars"
    sidecar_root.mkdir()
    sidecar_path = sidecar_root / "report.pdf.mara-elements.json"
    sidecar_path.write_text("{}", encoding="utf-8")

    paths = offline_layout_sidecar_paths(
        source_path,
        sidecar_roots=[sidecar_root],
    )

    assert paths == [sidecar_path]


def test_offline_layout_records_for_documents_use_external_sidecar_root(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "pdfs" / "report.pdf"
    source_path.parent.mkdir()
    source_path.write_bytes(b"%PDF")
    sidecar_root = tmp_path / "sidecars"
    sidecar_root.mkdir()
    (sidecar_root / "report.pdf.mara-elements.json").write_text(
        json.dumps(
            {
                "layout_elements": [
                    {
                        "page_label": "3",
                        "element_id": "answer-table",
                        "type": "table",
                        "caption": "Answer-bearing financial table",
                        "text": "Revenue 42 million",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARA_OFFLINE_LAYOUT_SIDECAR_DIR", str(sidecar_root))
    document = SimpleNamespace(
        metadata={
            "file_path": str(source_path),
            "file_name": "report.pdf",
        }
    )

    records = offline_element_records_for_documents(
        file_id="file-external-sidecar",
        documents=[document],
    )

    assert len(records) == 1
    assert records[0]["page_label"] == "3"
    assert records[0]["metadata"]["offline_layout_sidecar"] == (
        "report.pdf.mara-elements.json"
    )
