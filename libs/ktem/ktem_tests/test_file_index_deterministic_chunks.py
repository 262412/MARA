from __future__ import annotations

from pathlib import Path

from ktem.index.file.deterministic_chunks import stabilize_chunk_identities
from ktem.index.file.pipelines import IndexDocumentPipeline

from kotaemon.base import Document


def _fresh_chunks(order: tuple[int, ...], run_id: str) -> list[Document]:
    rows = (
        ("Results", "The model improves exact match.", 0, 37),
        ("Results", "The model improves exact match.", 0, 37),
        ("Methods", "We train on the QASPER corpus.", 38, 68),
    )
    return [
        Document(
            text=rows[index][1],
            doc_id=f"{run_id}-{index}",
            start_char_idx=rows[index][2],
            end_char_idx=rows[index][3],
            metadata={
                "file_id": f"runtime-{run_id}",
                "file_name": "paper.pdf",
                "page_label": "1",
                "section": rows[index][0],
                "type": "text",
            },
        )
        for index in order
    ]


def test_deterministic_chunk_identity_ignores_runtime_ids_and_input_order() -> None:
    first = stabilize_chunk_identities(
        _fresh_chunks((0, 1, 2), "first"),
        source_identity="paper.pdf",
    )
    second = stabilize_chunk_identities(
        _fresh_chunks((2, 1, 0), "second"),
        source_identity="paper.pdf",
    )

    assert [(chunk.text, chunk.doc_id) for chunk in first] == [
        (chunk.text, chunk.doc_id) for chunk in second
    ]
    assert len({chunk.doc_id for chunk in first}) == 3
    assert all(chunk.doc_id.startswith("stable-chunk:") for chunk in first)
    assert all("runtime-" not in chunk.doc_id for chunk in first)


def test_index_document_pipeline_propagates_opt_in_chunk_identity_policy() -> None:
    pipeline = IndexDocumentPipeline(
        embedding=object(),
        deterministic_chunk_ids=True,
    )

    routed = pipeline.route(Path("paper.txt"))

    assert routed.deterministic_chunk_ids is True
