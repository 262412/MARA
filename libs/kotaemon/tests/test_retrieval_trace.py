from kotaemon.base import Document, RetrievedDocument
from kotaemon.indices.retrieval_trace import (
    RetrievalCostStats,
    RetrievalTrace,
)


def _retrieved(
    doc_id: str,
    *,
    score: float,
    text: str = "content",
    metadata: dict | None = None,
    retrieval_metadata: dict | None = None,
) -> RetrievedDocument:
    return RetrievedDocument(
        text=text,
        id_=doc_id,
        score=score,
        metadata=metadata or {},
        retrieval_metadata=retrieval_metadata or {},
    )


def test_builds_trace_for_text_formula_and_figure_docs():
    docs = [
        _retrieved(
            "doc-text",
            score=0.91,
            metadata={
                "element_id": "text-1",
                "element_type": "text",
                "source_id": "source-a",
                "file_name": "paper-a.pdf",
                "page_number": "1",
                "page_label": "i",
                "bbox": [0, 1, 2, 3],
            },
            retrieval_metadata={"path": "dense", "distance": 0.09},
        ),
        _retrieved(
            "doc-formula",
            score=0.82,
            metadata={
                "type": "formula",
                "element_id": "formula-1",
                "source": "source-a",
                "filename": "paper-a.pdf",
                "page": 2,
                "bbox": "[4,5,6,7]",
            },
            retrieval_metadata={"retrieval_path": ["dense", "rerank"]},
        ),
        _retrieved(
            "doc-figure",
            score=0.7,
            metadata={
                "type": "figure",
                "element_id": "figure-1",
                "source_id": "source-b",
                "file_name": "paper-b.pdf",
                "page_label": "3",
                "bounding_box": {"x0": 10, "y0": 11, "x1": 12, "y1": 13},
            },
            retrieval_metadata={"modality": "image"},
        ),
    ]

    trace = RetrievalTrace.from_retrieved_docs(
        docs,
        query="energy equation",
        query_modality="text",
        retrieval_path=["hybrid", "rerank"],
        metadata={"request_id": "req-1"},
    )

    assert trace.query == "energy equation"
    assert [element.rank for element in trace.elements] == [1, 2, 3]
    assert [element.element_type for element in trace.elements] == [
        "text",
        "formula",
        "figure",
    ]
    assert trace.elements[0].doc_id == "doc-text"
    assert trace.elements[0].score == 0.91
    assert trace.elements[0].source_id == "source-a"
    assert trace.elements[0].file_name == "paper-a.pdf"
    assert trace.elements[0].page_number == 1
    assert trace.elements[0].page_label == "i"
    assert trace.elements[0].bbox == (0.0, 1.0, 2.0, 3.0)
    assert trace.elements[0].query_modality == "text"
    assert trace.elements[0].retrieval_path == ("dense",)
    assert trace.elements[1].retrieval_path == ("dense", "rerank")
    assert trace.elements[2].query_modality == "image"


def test_multi_document_summary_groups_by_source_and_file():
    trace = RetrievalTrace.from_retrieved_docs(
        [
            _retrieved(
                "a1",
                score=0.9,
                metadata={"source_id": "source-a", "file_name": "a.pdf"},
            ),
            _retrieved(
                "a2",
                score=0.8,
                metadata={"source_id": "source-a", "file_name": "a.pdf"},
            ),
            _retrieved(
                "b1",
                score=0.7,
                metadata={"source_id": "source-b", "file_name": "b.pdf"},
            ),
        ],
        query_modality="text",
    )

    assert trace.multi_document_summary == {
        "total_sources": 2,
        "total_files": 2,
        "sources": {
            "source-a": {
                "source_id": "source-a",
                "file_name": "a.pdf",
                "hit_count": 2,
                "element_count": 2,
                "top_rank": 1,
            },
            "source-b": {
                "source_id": "source-b",
                "file_name": "b.pdf",
                "hit_count": 1,
                "element_count": 1,
                "top_rank": 3,
            },
        },
        "files": {
            "a.pdf": {
                "file_name": "a.pdf",
                "source_ids": ["source-a"],
                "hit_count": 2,
                "element_count": 2,
                "top_rank": 1,
            },
            "b.pdf": {
                "file_name": "b.pdf",
                "source_ids": ["source-b"],
                "hit_count": 1,
                "element_count": 1,
                "top_rank": 3,
            },
        },
    }


def test_cost_stats_aggregate_latency_tokens_and_cost():
    trace = RetrievalTrace(
        query="q",
        elements=[],
        cost=RetrievalCostStats(
            retrieval_latency_ms=10.5,
            rerank_latency_ms=4.5,
            prompt_tokens=11,
            completion_tokens=7,
            embedding_tokens=13,
            total_cost=0.02,
            metadata={"provider": "test"},
        ),
    )

    trace.cost.add(
        RetrievalCostStats(
            retrieval_latency_ms=2,
            llm_latency_ms=20,
            prompt_tokens=3,
            completion_tokens=5,
            embedding_tokens=8,
            total_cost=0.01,
        )
    )

    assert trace.cost.total_latency_ms == 37.0
    assert trace.cost.total_tokens == 47
    assert trace.cost.to_dict() == {
        "retrieval_latency_ms": 12.5,
        "rerank_latency_ms": 4.5,
        "llm_latency_ms": 20.0,
        "total_latency_ms": 37.0,
        "prompt_tokens": 14,
        "completion_tokens": 12,
        "embedding_tokens": 21,
        "total_tokens": 47,
        "total_cost": 0.03,
        "metadata": {"provider": "test"},
    }


def test_missing_metadata_uses_safe_defaults_and_stable_dict_output():
    trace = RetrievalTrace.from_retrieved_docs(
        [
            Document(text="plain doc", id_="plain"),
            _retrieved(
                "unsafe",
                score=0.5,
                metadata={
                    "source_id": "source",
                    "file_name": "unsafe.pdf",
                    "bbox": object(),
                    "raw": object(),
                },
                retrieval_metadata={"debug": object()},
            ),
        ],
        query_modality="text",
        retrieval_path="fallback",
        metadata={"opaque": object()},
    )

    payload = trace.to_dict()

    assert payload["elements"][0]["doc_id"] == "plain"
    assert payload["elements"][0]["rank"] == 1
    assert payload["elements"][0]["score"] is None
    assert payload["elements"][0]["source_id"] is None
    assert payload["elements"][0]["file_name"] is None
    assert payload["elements"][0]["bbox"] is None
    assert payload["elements"][0]["retrieval_path"] == ["fallback"]
    assert payload["elements"][1]["bbox"] is None
    assert payload["metadata"] == {"opaque": "<object>"}
    assert payload["elements"][1]["metadata"]["raw"] == "<object>"
    assert payload["elements"][1]["retrieval_metadata"]["debug"] == "<object>"
