import json

from ktem.docqa.element_sidecar_schema import (
    ELEMENT_SIDECAR_SCHEMA_VERSION,
    sidecar_schema_report,
)
from ktem.docqa.offline_layout_index import offline_element_records_for_file


def test_canonical_ocr_layout_sidecar_schema_reports_coverage():
    payload = {
        "schema_version": ELEMENT_SIDECAR_SCHEMA_VERSION,
        "parser_backend": "docling",
        "pages": [
            {
                "page_label": "2",
                "elements": [
                    {
                        "element_id": "table-1",
                        "modality": "table",
                        "text": "North 10\nSouth 12",
                        "bbox": [10, 20, 30, 40],
                    },
                    {
                        "element_id": "figure-1",
                        "modality": "figure",
                        "caption": "Architecture diagram",
                    },
                ],
            }
        ],
    }

    report = sidecar_schema_report(payload)

    assert report == {
        "schema_version": "1",
        "parser_backend": "docling",
        "total_elements": 2,
        "element_counts_by_modality": {"figure": 1, "table": 1},
        "errors": [],
    }


def test_sidecar_schema_report_lists_invalid_records_without_rejecting_legacy_shape():
    payload = {
        "layout_elements": [
            {"page_label": "1", "type": "table", "text": "Valid table"},
            {"page_label": "2", "type": "figure"},
            {"type": "formula", "text": "x = y"},
        ]
    }

    report = sidecar_schema_report(payload)

    assert report["schema_version"] == "legacy"
    assert report["total_elements"] == 1
    assert report["element_counts_by_modality"] == {"table": 1}
    assert report["errors"] == [
        {
            "record_index": 1,
            "error": "missing_text_or_caption",
        },
        {
            "record_index": 2,
            "error": "missing_page_label",
        },
    ]


def test_offline_sidecar_records_preserve_schema_contract_metadata(tmp_path):
    source_path = tmp_path / "report.pdf"
    source_path.write_bytes(b"%PDF")
    sidecar_path = tmp_path / "report.pdf.mara-elements.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "parser_backend": "docling",
                "pages": [
                    {
                        "page_label": "4",
                        "elements": [
                            {
                                "element_id": "table-1",
                                "modality": "table",
                                "text": "North 10\nSouth 12",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    [record] = offline_element_records_for_file(
        file_id="file-1",
        file_name="report.pdf",
        file_path=source_path,
    )

    assert record["metadata"]["sidecar_schema_version"] == "1"
    assert record["metadata"]["parser_backend"] == "docling"
