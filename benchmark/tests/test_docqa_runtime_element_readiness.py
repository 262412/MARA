import types

from benchmark.docqa_runtime_sources import has_element_index
from benchmark.engines import get_engine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample
from benchmark.tests.test_docqa_runtime_engine_sources import (
    _FakeDoc,
    _FakeFileIndex,
    _FakeIndexRow,
    _install_reindex_runtime,
)


def test_has_element_index_requires_persisted_element_relation():
    without_elements = types.SimpleNamespace(
        file_index=_FakeFileIndex(
            [_FakeIndexRow("document", "text-healthy")],
            {
                "text-healthy": _FakeDoc(
                    "Page text.",
                    {
                        "file_id": "file-1",
                        "file_name": "doc.pdf",
                        "page_label": "4",
                    },
                )
            },
        )
    )
    with_elements = types.SimpleNamespace(
        file_index=_FakeFileIndex(
            [
                _FakeIndexRow("document", "text-healthy"),
                _FakeIndexRow("element_index", "element-1"),
            ],
            {
                "text-healthy": _FakeDoc(
                    "Page text.",
                    {
                        "file_id": "file-1",
                        "file_name": "doc.pdf",
                        "page_label": "4",
                    },
                ),
                "element-1": _FakeDoc("Table text.", {"file_id": "file-1"}),
            },
        )
    )

    assert has_element_index(without_elements, "file-1") is False
    assert has_element_index(with_elements, "file-1") is True


def test_element_route_reindexes_stale_file_without_element_relation(
    monkeypatch,
    tmp_path,
):
    doc_path = tmp_path / "doc.pdf"
    doc_path.write_text("runtime pdf", encoding="utf-8")
    fake_runtime = _install_reindex_runtime(monkeypatch, doc_path)
    fake_runtime.search_ready = True
    fake_runtime.file_index = _FakeFileIndex(
        [
            _FakeIndexRow("document", "text-healthy"),
            _FakeIndexRow("vector", "text-healthy"),
        ],
        {
            "text-healthy": _FakeDoc(
                "Page-scoped PDF text.",
                {
                    "file_id": "file-existing",
                    "file_name": "doc.pdf",
                    "page_label": "1",
                },
            )
        },
    )
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            route_policy="element",
        ),
    )

    result = engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            question="Question?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="pdf")
        ],
    )

    assert fake_runtime.indexed == [([str(doc_path)], True)]
    assert result.answer == "runtime answer"
