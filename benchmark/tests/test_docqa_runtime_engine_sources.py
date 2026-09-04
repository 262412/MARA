import sys
import types

from benchmark.docqa_runtime_sources import has_search_index
from benchmark.engines import get_engine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample
from benchmark.tests.runtime_source_fixtures import canonical_short_source_hit
from benchmark.tests.runtime_source_fixtures import runtime_hit as _runtime_hit


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


def test_docqa_runtime_engine_reindexes_existing_pdf_with_stale_text_metadata(
    monkeypatch, tmp_path
):
    doc_path = tmp_path / "doc.pdf"
    doc_path.write_text("runtime pdf", encoding="utf-8")
    fake_runtime = _install_reindex_runtime(monkeypatch, doc_path)
    fake_runtime.search_ready = True
    fake_runtime.file_index = _FakeFileIndex(
        [
            _FakeIndexRow("document", "text-stale"),
            _FakeIndexRow("document", "thumb-1"),
            _FakeIndexRow("vector", "text-stale"),
        ],
        {
            "text-stale": _FakeDoc(
                "Balance Sheet Current assets ...",
                {
                    "file_id": "file-existing",
                    "file_name": "doc.pdf",
                },
            ),
            "thumb-1": _FakeDoc(
                "Page thumbnail",
                {
                    "file_id": "file-existing",
                    "file_name": "doc.pdf",
                    "page_label": "4",
                    "type": "thumbnail",
                },
            ),
        },
    )

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert fake_runtime.indexed == [([str(doc_path)], True)]
    assert result.answer == "runtime answer"


def test_has_search_index_rejects_pdf_index_with_text_chunks_missing_page_metadata():
    runtime = types.SimpleNamespace(
        file_index=_FakeFileIndex(
            [
                _FakeIndexRow("document", "text-stale"),
                _FakeIndexRow("document", "thumb-1"),
                _FakeIndexRow("vector", "text-stale"),
            ],
            {
                "text-stale": _FakeDoc(
                    "Balance Sheet Current assets ...",
                    {"file_id": "file-1", "file_name": "doc.pdf"},
                ),
                "thumb-1": _FakeDoc(
                    "Page thumbnail",
                    {
                        "file_id": "file-1",
                        "file_name": "doc.pdf",
                        "page_label": "4",
                        "type": "thumbnail",
                    },
                ),
            },
        )
    )

    assert has_search_index(runtime, "file-1") is False


def test_has_search_index_accepts_pdf_index_with_page_scoped_text_chunks():
    runtime = types.SimpleNamespace(
        file_index=_FakeFileIndex(
            [
                _FakeIndexRow("document", "text-healthy"),
                _FakeIndexRow("document", "thumb-1"),
                _FakeIndexRow("vector", "text-healthy"),
            ],
            {
                "text-healthy": _FakeDoc(
                    "Balance Sheet Current assets Inventories Current liabilities.",
                    {
                        "file_id": "file-1",
                        "file_name": "doc.pdf",
                        "page_label": "4",
                    },
                ),
                "thumb-1": _FakeDoc(
                    "Page thumbnail",
                    {
                        "file_id": "file-1",
                        "file_name": "doc.pdf",
                        "page_label": "4",
                        "type": "thumbnail",
                    },
                ),
            },
        )
    )

    assert has_search_index(runtime, "file-1") is True


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
            "source_id": "file-1",
            "runtime_source_id": "file-1",
            "evaluation_source_id": "doc",
            "source_aliases": ["file-1", "doc"],
            "source_name": "doc.txt",
            "page_label": "2",
            "modality": "text",
            "element_id": "chunk-1",
            "canonical_id": "element:file-1:chunk-1",
            "runtime_identity": "element:file-1:chunk-1",
            "evaluation_identity": "element:doc:chunk-1",
            "identity": {
                "source_id": "file-1",
                "kind": "element",
                "local_id": "chunk-1",
            },
            "score": 0.91,
            "text": "Revenue increased.",
            "source_backrefs": ["doc#page:2"],
            "runtime_source_backrefs": ["file-1#page:2"],
            "evaluation_source_backrefs": ["doc#page:2"],
        }
    ]
    assert result.predicted_pages == ["2"]
    assert result.predicted_sources == ["doc#page:2"]
    assert result.predicted_element_ids == ["chunk-1"]


def test_docqa_runtime_engine_uses_source_ref_for_text_evidence_without_page(
    monkeypatch,
    tmp_path,
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={},
        evidence_bundle={
            "route": "doc_text",
            "items": [
                {
                    "evidence_id": "hit-1",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "modality": "text",
                    "text": "Whole-document text evidence.",
                    "source_backrefs": [],
                }
            ],
        },
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits[0]["source_backrefs"] == ["doc#source"]
    assert result.predicted_sources == ["doc#source"]
    assert result.predicted_pages == []


def test_docqa_runtime_engine_falls_back_to_selected_short_text_source(
    monkeypatch,
    tmp_path,
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={},
        evidence_bundle={"route": "doc_text", "items": []},
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)
    doc_path.write_text("Yelp", encoding="utf-8")

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits == [canonical_short_source_hit()]
    assert result.predicted_sources == ["doc#source"]
    assert result.predicted_pages == []


def test_docqa_runtime_engine_passes_image_documents_as_page_image_records(
    monkeypatch,
    tmp_path,
):
    image_path = tmp_path / "slide_page_7.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    fake_runtime = _install_response_runtime_for_path(
        monkeypatch,
        image_path,
        types.SimpleNamespace(
            answer="visual answer",
            references_text="",
            evidence_metadata={},
            evidence_bundle={
                "route": "doc_page_image",
                "items": [
                    {
                        "evidence_id": "page-image:slide_page_7:7",
                        "source_id": "slide_page_7",
                        "source_name": "slide_page_7.jpg",
                        "page_label": "7",
                        "modality": "page_image",
                        "page_image_path": str(image_path),
                        "source_backrefs": ["slide_page_7#page:7"],
                    }
                ],
            },
        ),
    )
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            route_policy="visual",
        ),
    )

    result = engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="slide_page_7",
            question="What does the slide show?",
            answers=["visual answer"],
            evidence_pages=[7],
        ),
        documents=[
            BenchmarkDocument(
                document_id="slide_page_7",
                path=image_path,
                format_type="jpg",
                modality="page_image",
                metadata={"page": 7},
            )
        ],
    )

    assert fake_runtime.indexed == []
    assert fake_runtime.requests[0].selected_file_ids == []
    assert fake_runtime.requests[0].page_image_records == [
        {
            "evidence_id": "page-image:slide_page_7:7",
            "file_id": "slide_page_7",
            "file_name": "slide_page_7.jpg",
            "page_label": "7",
            "page_number": 7,
            "page_image_path": str(image_path),
            "rendered_page_image": str(image_path),
            "modality": "page_image",
            "text": "",
            "ocr_text": "",
            "source_backrefs": ["slide_page_7#page:7"],
            "metadata": {
                "image_ref": str(image_path),
                "visual_backend_type": "provided_image",
            },
        }
    ]
    assert result.predicted_pages == ["7"]
    assert result.predicted_sources == ["slide_page_7#page:7"]


def test_docqa_runtime_engine_drops_image_payload_from_text_retrieved_hits(
    monkeypatch,
    tmp_path,
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={},
        evidence_bundle={
            "route": "doc_text",
            "items": [
                {
                    "evidence_id": "hit-1",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "text": "Text evidence.",
                    "image": "base64-image",
                    "page_image_path": "data:image/png;base64,abc",
                }
            ],
        },
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits[0]["text"] == "Text evidence."
    assert "image" not in result.retrieved_hits[0]
    assert "page_image_path" not in result.retrieved_hits[0]


def test_docqa_runtime_engine_adds_metadata_page_coverage_to_predicted_citations(
    monkeypatch,
    tmp_path,
):
    response = types.SimpleNamespace(
        answer="runtime answer",
        references_text="",
        evidence_metadata={"page_coverage": ["2", "5", 8, "", None]},
        evidence_bundle={"route": "hybrid", "items": [_runtime_hit()]},
    )
    doc_path = _install_docqa_runtime_with_response(monkeypatch, tmp_path, response)

    result = _run_docqa_runtime(doc_path, tmp_path)

    assert result.retrieved_hits[0]["source_backrefs"] == ["doc#page:2"]
    assert result.predicted_pages == ["2", "5", "8"]
    assert result.predicted_sources == ["doc#page:2", "doc#page:5", "doc#page:8"]


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
            "source_id": "file-1",
            "runtime_source_id": "file-1",
            "evaluation_source_id": "doc",
            "source_aliases": ["file-1", "doc"],
            "source_name": "Generic entity",
            "canonical_id": "evidence:file-1:graph-hit",
            "runtime_identity": "evidence:file-1:graph-hit",
            "evaluation_identity": "evidence:doc:graph-hit",
            "identity": {
                "source_id": "file-1",
                "kind": "evidence",
                "local_id": "graph-hit",
            },
            "text": "Graph evidence.",
            "source_backrefs": ["doc#page:2", "doc#page:3"],
            "runtime_source_backrefs": [
                "file-1#page:2",
                "file-1#page:3",
            ],
            "evaluation_source_backrefs": ["doc#page:2", "doc#page:3"],
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
    _install_fake_docqa_modules(
        monkeypatch,
        runtime=fake_runtime,
    )
    return fake_runtime


def _install_docqa_runtime_with_response(monkeypatch, tmp_path, response):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    _install_response_runtime_for_path(monkeypatch, doc_path, response)
    return doc_path


def _install_response_runtime_for_path(monkeypatch, doc_path, response):
    runtime = _ResponseRuntime(doc_path, response)
    _install_fake_docqa_modules(monkeypatch, runtime=runtime)
    return runtime


def _install_fake_docqa_modules(monkeypatch, *, runtime):
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: runtime,
            DocQARequest=_FakeRequest,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa.offline_layout_index",
        types.SimpleNamespace(offline_element_records_for_file=lambda **_: []),
    )


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


class _FakeIndexRow:
    def __init__(self, relation_type, target_id):
        self.relation_type = relation_type
        self.target_id = target_id


class _FakeDoc:
    def __init__(self, text, metadata):
        self.text = text
        self.metadata = metadata


class _FakeDocStore:
    def __init__(self, docs):
        self.docs = docs

    def get(self, ids):
        return [self.docs[item] for item in ids if item in self.docs]


class _FakeFileIndex:
    def __init__(self, rows, docs):
        self._resources = {
            "Index": rows,
            "DocStore": _FakeDocStore(docs),
            "VectorStore": object(),
        }


class _ReindexRuntime:
    def __init__(self, doc_path):
        self.doc_path = doc_path
        self.indexed = []
        self.requests = []
        self.search_ready = False
        self.file_index = None

    def has_search_index(self, file_id):
        assert file_id == "file-existing"
        if self.file_index is None:
            return self.search_ready
        return has_search_index(
            types.SimpleNamespace(file_index=self.file_index), file_id
        )

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
        self.indexed = []
        self.requests = []

    def index_paths(self, paths, reindex=False):
        self.indexed.append((paths, reindex))

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
        self.requests.append(request)
        return self.response


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
