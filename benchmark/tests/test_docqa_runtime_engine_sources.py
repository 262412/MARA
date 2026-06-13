import sys
import types

from benchmark.engines import get_engine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample


def test_docqa_runtime_engine_reindexes_existing_file_without_search_index(
    monkeypatch, tmp_path
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    fake_runtime = _install_reindex_runtime(monkeypatch, doc_path)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert fake_runtime.indexed == [([str(doc_path)], True)]
    assert fake_runtime.requests[0].selected_file_ids == ["file-existing"]
    assert result.answer == "runtime answer"


def test_docqa_runtime_engine_derives_hits_pages_sources_and_elements(
    monkeypatch, tmp_path
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={},
        evidence_bundle={"route": "doc_text", "items": [_runtime_hit()]},
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits == [
        {
            "evidence_id": "hit-1",
            "document_id": "doc",
            "source_id": "doc",
            "runtime_source_id": "file-1",
            "source_name": "doc.txt",
            "page_label": "2",
            "modality": "text",
            "element_id": "chunk-1",
            "score": 0.91,
            "text": "Revenue increased.",
            "source_backrefs": ["doc#page:2"],
        }
    ]
    assert result.predicted_pages == ["2"]
    assert result.predicted_sources == ["doc#page:2"]
    assert result.predicted_element_ids == ["chunk-1"]


def test_docqa_runtime_engine_falls_back_to_evidence_metadata_when_bundle_empty(
    monkeypatch, tmp_path
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_bundle={"route": "doc_text", "items": []},
        evidence_metadata={"evidence": [_metadata_hit()]},
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits[0]["evidence_id"] == "metadata-hit"
    assert result.retrieved_hits[0]["runtime_source_id"] == "file-1"
    assert result.predicted_pages == ["4"]
    assert result.predicted_sources == ["doc#page:4"]


def test_docqa_runtime_engine_canonicalizes_source_backrefs_without_source_id(
    monkeypatch, tmp_path
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={},
        evidence_bundle={
            "route": "graph_global",
            "items": [
                {
                    "evidence_id": "graph-hit",
                    "source_name": "Generic entity",
                    "text": "Graph evidence.",
                    "source_backrefs": ["file-1#page:2", "file-1#page:3"],
                }
            ],
        },
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits == [
        {
            "evidence_id": "graph-hit",
            "document_id": "doc",
            "source_id": "doc",
            "source_name": "Generic entity",
            "text": "Graph evidence.",
            "source_backrefs": ["doc#page:2", "doc#page:3"],
        }
    ]
    assert result.predicted_sources == ["doc#page:2", "doc#page:3"]


def _run_docqa_runtime(doc_path, tmp_path):
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(suite_name="runtime", output_dir=tmp_path / "out"),
    )
    return engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            question="Question?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
    )


def _install_reindex_runtime(monkeypatch, doc_path):
    fake_runtime = _ReindexRuntime(doc_path)
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: fake_runtime,
            DocQARequest=_FakeRequest,
        ),
    )
    return fake_runtime


def _install_docqa_runtime_with_response(monkeypatch, tmp_path, response):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: _ResponseRuntime(doc_path, response),
            DocQARequest=_FakeRequest,
        ),
    )
    return doc_path


class _FakeRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Record:
    def __init__(self, file_id, path):
        self.file_id = file_id
        self.name = "doc.txt"
        self.path = str(path)
        self.size = 1
        self.tokens = 1
        self.loader = "test"
        self.date_created = None


class _ReindexRuntime:
    def __init__(self, doc_path):
        self.doc_path = doc_path
        self.indexed = []
        self.requests = []
        self.search_ready = False

    def has_search_index(self, file_id):
        assert file_id == "file-existing"
        return self.search_ready

    def index_paths(self, paths, reindex=False):
        self.indexed.append((paths, reindex))
        self.search_ready = True

    def resolve_file_refs(self, refs):
        if refs and refs[0] in {"doc", "doc.txt", str(self.doc_path)}:
            return [_Record("file-existing", self.doc_path)]
        if refs and refs[0] == "file-existing":
            return [_Record("file-existing", self.doc_path)]
        return []

    def list_files(self, user_id=None):
        del user_id
        return [_Record("file-existing", self.doc_path)]

    def run_turn(self, request):
        self.requests.append(request)
        return types.SimpleNamespace(
            answer="runtime answer", references_text="doc.txt#page:1"
        )


class _ResponseRuntime:
    def __init__(self, doc_path, response):
        self.doc_path = doc_path
        self.response = response

    def index_paths(self, paths, reindex=False):
        del paths, reindex

    def resolve_file_refs(self, refs):
        if refs and refs[0] in {"doc", "doc.txt", str(self.doc_path)}:
            return [_Record("file-1", self.doc_path)]
        if refs and refs[0] == "file-1":
            return [_Record("file-1", self.doc_path)]
        return []

    def list_files(self, user_id=None):
        del user_id
        return [_Record("file-1", self.doc_path)]

    def run_turn(self, request):
        del request
        return self.response


def _runtime_hit():
    return {
        "evidence_id": "hit-1",
        "source_id": "file-1",
        "source_name": "doc.txt",
        "page_label": "2",
        "modality": "text",
        "element_id": "chunk-1",
        "score": 0.91,
        "text": "Revenue increased.",
        "source_backrefs": ["file-1#page:2"],
    }


def _metadata_hit():
    return {
        "evidence_id": "metadata-hit",
        "file_id": "file-1",
        "file_name": "doc.txt",
        "page_label": "4",
        "element_type": "text",
        "text": "Metadata fallback evidence.",
        "source_backrefs": ["file-1#page:4"],
    }
