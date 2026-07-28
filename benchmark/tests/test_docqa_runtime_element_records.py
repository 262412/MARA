import json
import sys
import types

from benchmark.docqa_image_documents import element_index_records_from_documents
from benchmark.engines import get_engine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample


def test_element_index_records_from_documents_normalizes_layout_metadata(tmp_path):
    image_path = tmp_path / "slide_page_7.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0jpeg")

    records = element_index_records_from_documents(
        [
            BenchmarkDocument(
                document_id="slide_page_7",
                path=image_path,
                format_type="jpg",
                modality="page_image",
                metadata={
                    "page": 7,
                    "layout_elements": [
                        {
                            "element_id": "table-1",
                            "element_type": "table",
                            "bbox": [10, 20, 200, 120],
                            "caption": "Trading operating profit",
                            "text": "Trading Operating Profit 12.5 bn",
                        }
                    ],
                },
            )
        ]
    )

    record = records[0]
    assert record["evidence_id"] == "element:slide_page_7:7:table-1"
    assert record["source_id"] == "slide_page_7"
    assert record["file_id"] == "slide_page_7"
    assert record["file_name"] == "slide_page_7.jpg"
    assert record["page_label"] == "7"
    assert record["page_number"] == 7
    assert record["element_id"] == "table-1"
    assert record["element_type"] == "table"
    assert record["modality"] == "table"
    assert record["bbox"] == [10, 20, 200, 120]
    assert record["caption"] == "Trading operating profit"
    assert record["text"] == "Trading Operating Profit 12.5 bn"
    assert record["source_backrefs"] == ["slide_page_7#page:7"]
    assert record["identity"] == {
        "source_id": "slide_page_7",
        "kind": "element",
        "local_id": "table-1",
    }
    assert record["canonical_id"] == "element:slide_page_7:table-1"


def test_element_record_normalization_preserves_v2_structure_fields(tmp_path):
    image_path = tmp_path / "report_page_7.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0jpeg")

    records = element_index_records_from_documents(
        [
            BenchmarkDocument(
                document_id="report",
                path=image_path,
                format_type="jpg",
                modality="page_image",
                metadata={
                    "page": 7,
                    "layout_elements": [
                        {
                            "element_id": "cell-7-2",
                            "element_type": "table",
                            "text": "Revenue 42 million",
                            "parent_element_id": "table-7",
                            "neighbor_element_ids": ["cell-7-1", "cell-7-3"],
                            "section_id": "financial-results",
                            "table_id": "table-7",
                            "row_index": 2,
                            "column_index": 1,
                            "continuation_id": "revenue-table",
                            "chunk_start": 120,
                            "chunk_end": 138,
                        }
                    ],
                },
            )
        ]
    )

    assert records[0]["parent_element_id"] == "table-7"
    assert records[0]["neighbor_element_ids"] == ["cell-7-1", "cell-7-3"]
    assert records[0]["section_id"] == "financial-results"
    assert records[0]["table_id"] == "table-7"
    assert records[0]["row_index"] == 2
    assert records[0]["column_index"] == 1
    assert records[0]["continuation_id"] == "revenue-table"
    assert records[0]["chunk_start"] == 120
    assert records[0]["chunk_end"] == 138


def test_docqa_runtime_engine_passes_document_element_index_records(
    monkeypatch,
    tmp_path,
):
    image_path = tmp_path / "slide_page_7.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    element_record = {
        "evidence_id": "element:slide_page_7:7:table-1",
        "file_id": "slide_page_7",
        "file_name": "slide_page_7.jpg",
        "page_label": "7",
        "element_id": "table-1",
        "modality": "table",
        "bbox": [10, 20, 200, 120],
        "caption": "Trading operating profit",
        "text": "Trading Operating Profit 12.5 bn",
        "source_backrefs": ["slide_page_7#page:7"],
        "metadata": {"parser": "fixture"},
    }
    fake_runtime = _install_response_runtime_for_path(
        monkeypatch,
        image_path,
        types.SimpleNamespace(
            answer="12.5 bn",
            references_text="",
            evidence_metadata={},
            evidence_bundle={"route": "doc_element", "items": []},
        ),
    )
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            route_policy="element",
        ),
    )

    engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="slide_page_7",
            question="How much is the Trading Operating Profit?",
            answers=["12.5 bn"],
            evidence_pages=[7],
        ),
        documents=[
            BenchmarkDocument(
                document_id="slide_page_7",
                path=image_path,
                format_type="jpg",
                modality="page_image",
                metadata={"page": 7, "element_index_records": [element_record]},
            )
        ],
    )

    assert fake_runtime.indexed == []
    assert fake_runtime.requests[0].selected_file_ids == []
    indexed_record = fake_runtime.requests[0].element_index_records[0]
    for field, value in element_record.items():
        assert indexed_record[field] == value
    assert indexed_record["source_id"] == "slide_page_7"
    assert indexed_record["page_number"] == 7
    assert indexed_record["canonical_id"] == "element:slide_page_7:table-1"


def test_docqa_runtime_engine_passes_external_offline_sidecar_records(
    monkeypatch,
    tmp_path,
):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF")
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
                        "caption": "Answer-bearing table",
                        "text": "Revenue 42 million",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARA_OFFLINE_LAYOUT_SIDECAR_DIR", str(sidecar_root))
    fake_runtime = _install_response_runtime_for_path(
        monkeypatch,
        pdf_path,
        types.SimpleNamespace(
            answer="42 million",
            references_text="",
            evidence_metadata={},
            evidence_bundle={"route": "doc_element", "items": []},
        ),
    )
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            route_policy="element",
        ),
    )

    engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="report",
            question="What was revenue?",
            answers=["42 million"],
            evidence_pages=[3],
        ),
        documents=[
            BenchmarkDocument(
                document_id="report",
                path=pdf_path,
                format_type="pdf",
                modality="mixed",
                metadata={},
            )
        ],
    )

    records = fake_runtime.requests[0].element_index_records
    assert len(records) == 1
    assert records[0]["file_id"] == "report"
    assert records[0]["page_label"] == "3"
    assert records[0]["modality"] == "table"
    assert records[0]["metadata"]["index_source"] == "offline_layout_sidecar"


def _install_response_runtime_for_path(monkeypatch, doc_path, response):
    runtime = _ResponseRuntime(doc_path, response)
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: runtime,
            DocQARequest=_FakeRequest,
        ),
    )
    return runtime


class _FakeRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _ResponseRuntime:
    def __init__(self, doc_path, response):
        self.doc_path = doc_path
        self.response = response
        self.indexed = []
        self.requests = []

    def index_paths(self, paths, reindex=False):
        self.indexed.append((paths, reindex))

    def list_files(self, user_id=None):
        del user_id
        return []

    def resolve_file_refs(self, refs):
        del refs
        return []

    def run_turn(self, request):
        self.requests.append(request)
        return self.response
