from types import SimpleNamespace

import ktem.index.file.pipelines as file_pipelines_module
from ktem.index.file._deletion import FileIndexDeletionController

from kotaemon.base import Document


class _IndexRow:
    def __init__(self, source_id, target_id, relation_type):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type


class _IndexingSession:
    def __init__(self):
        self.added_rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_all(self, rows):
        self.added_rows.extend(rows)

    @staticmethod
    def commit():
        return None


class _DocStoreWriter:
    def __init__(self):
        self.batches = []

    def add(self, docs):
        self.batches.append(list(docs))


class _DeleteResult:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _DeleteSession:
    def __init__(self, source_row, index_rows):
        self._source_row = source_row
        self._index_rows = index_rows
        self._execute_count = 0
        self.deleted_rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _statement):
        self._execute_count += 1
        if self._execute_count == 1:
            return _DeleteResult([(self._source_row,)])
        return _DeleteResult([(row,) for row in self._index_rows])

    def delete(self, row):
        self.deleted_rows.append(row)

    @staticmethod
    def commit():
        return None


class _Statement:
    def where(self, *_args, **_kwargs):
        return self


class _ComparableColumn:
    def __eq__(self, _other):
        return True


class _DeleteSourceTable:
    id = _ComparableColumn()


class _DeleteIndexTable:
    source_id = _ComparableColumn()


class _DeleteStore:
    def __init__(self):
        self.deleted = []

    def delete(self, ids):
        self.deleted.append(list(ids))


def _write_offline_layout_sidecar(tmp_path):
    source_path = tmp_path / "report.pdf"
    source_path.write_bytes(b"%PDF")
    (tmp_path / "report.pdf.mara-elements.json").write_text(
        """
        {
          "parser": "docling",
          "pages": [
            {
              "page": 4,
              "elements": [
                {
                  "type": "table",
                  "caption": "Regional revenue",
                  "text": "North 10\\nSouth 12",
                  "bbox": [10, 20, 30, 40]
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    return source_path


def _expected_offline_element_record():
    return {
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
            "index_source": "offline_layout_sidecar",
            "offline_layout_record_index": 0,
            "offline_layout_sidecar": "report.pdf.mara-elements.json",
            "parser_backend": "docling",
        },
    }


def test_index_pipeline_persists_element_and_graph_index_docs(monkeypatch, tmp_path):
    session = _IndexingSession()
    docstore = _DocStoreWriter()
    pipeline = file_pipelines_module.IndexPipeline(
        loader=SimpleNamespace(),
        splitter=None,
        Source=SimpleNamespace(),
        Index=_IndexRow,
        VS=None,
        DS=docstore,
        FSPath=tmp_path,
        user_id="user-1",
        embedding=SimpleNamespace(),
    )
    monkeypatch.setattr(
        file_pipelines_module,
        "Session",
        lambda _engine: session,
    )

    chunk = Document(
        text="Table: Regional revenue\nNorth 10\nSouth 12",
        id_="table-doc",
        metadata={
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "element_type": "table",
            "caption": "Regional revenue",
        },
    )

    pipeline.handle_chunks_docstore([chunk], "file-1")

    assert len(docstore.batches) == 3
    element_docs = docstore.batches[1]
    graph_docs = docstore.batches[2]
    assert element_docs[0].metadata["type"] == "mara_element_index"
    assert element_docs[0].metadata["source_id"] == "file-1"
    assert graph_docs[0].metadata["type"] == "mara_graph_index"
    assert graph_docs[0].metadata["source_id"] == "file-1"
    assert [row.relation_type for row in session.added_rows] == [
        "document",
        "element_index",
        "graph_index",
    ]


def test_index_pipeline_persists_offline_element_records(monkeypatch, tmp_path):
    source_path = _write_offline_layout_sidecar(tmp_path)
    session = _IndexingSession()
    docstore = _DocStoreWriter()
    pipeline = file_pipelines_module.IndexPipeline(
        loader=SimpleNamespace(),
        splitter=None,
        Source=SimpleNamespace(),
        Index=_IndexRow,
        VS=None,
        DS=docstore,
        FSPath=tmp_path,
        user_id="user-1",
        embedding=SimpleNamespace(),
    )
    monkeypatch.setattr(
        file_pipelines_module,
        "Session",
        lambda _engine: session,
    )

    chunk = Document(
        text="ordinary page text",
        id_="text-doc",
        metadata={
            "file_id": "file-1",
            "file_name": "report.pdf",
            "file_path": str(source_path),
            "page_label": "4",
        },
    )

    pipeline.handle_chunks_docstore([chunk], "file-1")

    assert len(docstore.batches) == 2
    element_docs = docstore.batches[1]
    assert element_docs[0].metadata["type"] == "mara_element_index"
    assert element_docs[0].metadata["element_index_record"] == (
        _expected_offline_element_record()
    )
    assert [row.relation_type for row in session.added_rows] == [
        "document",
        "element_index",
    ]


def test_delete_event_removes_element_index_docs_from_docstore(monkeypatch):
    source_row = SimpleNamespace(name="report.pdf")
    rows = [
        SimpleNamespace(relation_type="document", target_id="doc-1"),
        SimpleNamespace(relation_type="element_index", target_id="element-1"),
        SimpleNamespace(relation_type="graph_index", target_id="graph-1"),
        SimpleNamespace(relation_type="vector", target_id="vector-1"),
    ]
    session = _DeleteSession(source_row, rows)
    vector_store = _DeleteStore()
    docstore = _DeleteStore()
    controller = FileIndexDeletionController(
        index=SimpleNamespace(
            _resources={"Source": _DeleteSourceTable, "Index": _DeleteIndexTable},
            _vs=vector_store,
            _docstore=docstore,
        ),
        selected_panel_false="Selected",
    )
    monkeypatch.setattr("ktem.index.file._deletion.Session", lambda _engine: session)
    monkeypatch.setattr("ktem.index.file._deletion.select", lambda _table: _Statement())
    monkeypatch.setattr("ktem.index.file._deletion.gr.Info", lambda _message: None)

    result = controller.delete_event("file-1")

    assert result == (None, "Selected")
    assert vector_store.deleted == [["vector-1"]]
    assert docstore.deleted == [["doc-1", "element-1", "graph-1"]]
