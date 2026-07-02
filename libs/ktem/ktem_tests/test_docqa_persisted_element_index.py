from types import SimpleNamespace
from typing import Any

from ktem.docqa import _runtime_elements

from kotaemon.base import RetrievedDocument


def test_runtime_elements_prefers_persisted_element_index_records(monkeypatch):
    persisted_doc = RetrievedDocument(
        text="Persisted table text.",
        id_="element-index-doc",
        metadata={
            "type": "mara_element_index",
            "source_id": "file-1",
            "element_index_relation_type": "element_index",
            "element_index_record": {
                "evidence_id": "element:file-1:7:persisted-table",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "7",
                "element_id": "persisted-table",
                "modality": "table",
                "bbox": [1, 2, 3, 4],
                "caption": "Persisted revenue",
                "text": "Persisted table text.",
                "source_backrefs": ["file-1#page:7"],
                "metadata": {"index_source": "persisted_fixture"},
            },
        },
    )
    fallback_doc = RetrievedDocument(
        text="Table: stale fallback",
        id_="fallback-doc",
        metadata={
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "element_type": "table",
            "caption": "Fallback revenue",
        },
    )
    docstore = _RecordingDocStore(
        {
            "element-index-doc": persisted_doc,
            "fallback-doc": fallback_doc,
        }
    )
    file_index = SimpleNamespace(_resources={"Index": object(), "DocStore": docstore})

    def relation_ids(_index_table, _selected_ids, relation_type):
        if relation_type == "element_index":
            return ["element-index-doc"]
        if relation_type == "document":
            return ["fallback-doc"]
        return []

    monkeypatch.setattr(
        _runtime_elements,
        "_relation_doc_ids_for_sources",
        relation_ids,
    )
    monkeypatch.setattr(
        _runtime_elements,
        "_document_ids_for_sources",
        lambda _index_table, _selected_ids: ["fallback-doc"],
    )

    records = _runtime_elements.element_index_records_for_selected_files(
        file_index,
        ["file-1"],
    )

    assert records == [
        {
            **persisted_doc.metadata["element_index_record"],
            "source_id": "file-1",
            "page_number": 7,
            "element_type": "table",
        }
    ]
    assert docstore.requests == [["element-index-doc"]]


class _RecordingDocStore:
    def __init__(self, docs: dict[str, Any]) -> None:
        self._docs = docs
        self.requests: list[list[str]] = []

    def get(self, ids):
        requested = list(ids if isinstance(ids, list) else [ids])
        self.requests.append(requested)
        return [self._docs[doc_id] for doc_id in requested]
