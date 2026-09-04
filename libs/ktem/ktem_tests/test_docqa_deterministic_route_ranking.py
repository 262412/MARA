from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa.element_retriever import rank_element_records
from ktem.docqa.evidence import _rank_route_items
from ktem.docqa.graph_index import select_graph_index_evidence
from ktem.docqa.visual_retriever import rank_page_image_records


class _NearTieBackend:
    name = "near_tie"
    backend_type = "test"

    def score(self, _query, record):
        return (
            0.90000049
            if str(record.get("element_id") or "").endswith("b")
            else 0.90000041
        )


def _element(name: str) -> dict[str, object]:
    return {
        "evidence_id": f"element:paper:{name}",
        "source_id": "paper",
        "element_id": name,
        "element_type": "table",
        "text": "revenue table",
    }


def _page(name: str) -> dict[str, object]:
    return {
        "evidence_id": f"page-image:paper:{name}",
        "source_id": "paper",
        "element_id": name,
        "modality": "page_image",
        "text": "revenue chart",
    }


def test_element_near_tie_is_independent_of_backend_input_order() -> None:
    records = [_element("b"), _element("a")]

    forward, _ = rank_element_records("revenue", records, retriever=_NearTieBackend())
    reverse, _ = rank_element_records(
        "revenue", list(reversed(records)), retriever=_NearTieBackend()
    )

    assert [item["element_id"] for item in forward] == ["a", "b"]
    assert [item["element_id"] for item in reverse] == ["a", "b"]


def test_visual_near_tie_is_independent_of_backend_input_order() -> None:
    records = [_page("b"), _page("a")]

    forward, _ = rank_page_image_records(
        "revenue", records, retriever=_NearTieBackend()
    )
    reverse, _ = rank_page_image_records(
        "revenue", list(reversed(records)), retriever=_NearTieBackend()
    )

    assert [item["element_id"] for item in forward] == ["a", "b"]
    assert [item["element_id"] for item in reverse] == ["a", "b"]


def test_graph_equal_score_is_independent_of_index_record_order() -> None:
    entities = [
        {"id": "b", "label": "Revenue", "summary": "Revenue increased."},
        {"id": "a", "label": "Revenue", "summary": "Revenue increased."},
    ]

    forward = select_graph_index_evidence(
        "revenue", {"graph_index": {"entities": entities}}, max_items=1
    )
    reverse = select_graph_index_evidence(
        "revenue", {"graph_index": {"entities": list(reversed(entities))}}, max_items=1
    )

    assert forward["evidence_ids"] == ["graph-entity:a"]
    assert reverse["evidence_ids"] == ["graph-entity:a"]


def test_final_route_near_tie_uses_quantized_score_then_identity() -> None:
    first = _element("a")
    second = _element("b")
    first["metadata"] = {"visual_retriever_score": 0.90000041}
    second["metadata"] = {"visual_retriever_score": 0.90000049}
    request = SimpleNamespace(prompt="revenue", selected_text="")

    forward = _rank_route_items([second, first], request, "doc_element")
    reverse = _rank_route_items([first, second], request, "doc_element")

    assert [item["element_id"] for item in forward] == ["a", "b"]
    assert [item["element_id"] for item in reverse] == ["a", "b"]
