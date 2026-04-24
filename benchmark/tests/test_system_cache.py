from benchmark.schemas import BenchmarkConfig, BenchmarkDocument
from benchmark.system import KotaemonTextRAGSystem
from kotaemon.base import Document


class _CountingReader:
    def __init__(self):
        self.calls = 0

    def load_data(self, path, extra_info=None, **kwargs):
        del path, kwargs
        self.calls += 1
        document = Document("cached alpha text", metadata={"page_label": "1"})
        if extra_info:
            document.metadata.update(extra_info)
        return [document]


def test_text_rag_system_uses_parse_cache_for_same_file_across_documents(
    monkeypatch, tmp_path
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("alpha", encoding="utf-8")
    reader = _CountingReader()
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="cache",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            cache_mode="warm",
        )
    )
    monkeypatch.setattr(system, "_get_reader", lambda _path: reader)

    first = system._build_index(
        BenchmarkDocument(document_id="doc-a", path=doc_path, format_type="txt")
    )
    second = system._build_index(
        BenchmarkDocument(document_id="doc-b", path=doc_path, format_type="txt")
    )

    assert reader.calls == 1
    assert first.parse_cache_hit is False
    assert first.parse_cache_stats == {"hits": 0, "misses": 1, "writes": 1}
    assert second.parse_cache_hit is True
    assert second.parse_cache_stats == {"hits": 1, "misses": 0, "writes": 0}
    assert second.parsed_documents[0].metadata["file_id"] == "doc-b"


def test_text_rag_system_bypasses_parse_cache_when_requested(monkeypatch, tmp_path):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("alpha", encoding="utf-8")
    reader = _CountingReader()
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="cache",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            cache_mode="bypass",
        )
    )
    monkeypatch.setattr(system, "_get_reader", lambda _path: reader)

    first = system._build_index(
        BenchmarkDocument(document_id="doc-a", path=doc_path, format_type="txt")
    )
    second = system._build_index(
        BenchmarkDocument(document_id="doc-b", path=doc_path, format_type="txt")
    )

    assert reader.calls == 2
    assert first.parse_cache_hit is False
    assert second.parse_cache_hit is False
    assert first.parse_cache_stats == {"hits": 0, "misses": 0, "writes": 0}
    assert second.parse_cache_stats == {"hits": 0, "misses": 0, "writes": 0}
