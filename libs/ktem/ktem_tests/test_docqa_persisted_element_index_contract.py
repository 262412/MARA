import json

from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from ktem.docqa.multimodal_index import (
    element_index_documents_from_records,
    element_index_persistence_contract,
)


def _element_record():
    return {
        "evidence_id": "element:file-1:4:table-1",
        "file_id": "file-1",
        "file_name": "report.pdf",
        "page_label": "4",
        "element_id": "table-1",
        "modality": "table",
        "bbox": [10, 20, 30, 40],
        "caption": "Regional revenue",
        "text": "North 10\nSouth 12",
        "source_backrefs": ["file-1#page:4"],
        "metadata": {"index_source": "offline_layout_sidecar"},
    }


def test_element_index_persistence_contract_names_docstore_shape():
    assert element_index_persistence_contract() == {
        "doc_type": "mara_element_index",
        "relation_type": "element_index",
        "schema_version": "1.0",
        "metadata_required_keys": [
            "type",
            "source_id",
            "file_id",
            "file_name",
            "page_label",
            "element_index_relation_type",
            "element_index_schema_version",
            "element_index_record",
        ],
        "record_required_keys": [
            "evidence_id",
            "file_id",
            "file_name",
            "page_label",
            "element_id",
            "modality",
            "text",
            "source_backrefs",
            "metadata",
        ],
    }


def test_element_index_document_metadata_satisfies_persistence_contract():
    [doc] = element_index_documents_from_records("file-1", [_element_record()])
    contract = element_index_persistence_contract()

    assert list(doc.metadata) == contract["metadata_required_keys"]
    assert doc.metadata["type"] == contract["doc_type"]
    assert doc.metadata["element_index_relation_type"] == contract["relation_type"]
    assert doc.metadata["element_index_schema_version"] == contract["schema_version"]
    assert set(contract["record_required_keys"]).issubset(
        doc.metadata["element_index_record"]
    )


def test_element_index_document_metadata_normalizes_pypdf_objects():
    record = _element_record()
    record["bbox"] = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/BBox"),
            NameObject("/Label"): TextStringObject("A"),
        }
    )
    record["metadata"] = {
        "parser_object": DictionaryObject(
            {NameObject("/Subtype"): NameObject("/Table")}
        )
    }

    [doc] = element_index_documents_from_records("file-1", [record])
    persisted = doc.metadata["element_index_record"]

    assert type(persisted["bbox"]) is dict
    assert persisted["bbox"] == {"/Label": "A", "/Type": "/BBox"}
    assert type(persisted["metadata"]["parser_object"]) is dict
    assert persisted["metadata"]["parser_object"] == {"/Subtype": "/Table"}
    json.dumps(doc.metadata, sort_keys=True)
