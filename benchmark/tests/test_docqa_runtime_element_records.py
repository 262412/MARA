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

    assert records == [
        {
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
            "metadata": {},
        }
    ]


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
    assert fake_runtime.requests[0].element_index_records == [element_record]


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
