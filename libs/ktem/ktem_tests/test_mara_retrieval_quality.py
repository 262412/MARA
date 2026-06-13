from ktem.reasoning.mara import MaraAgentPipeline, _collect_text_rag_generation
from ktem.reasoning.simple import FullQAPipeline

from kotaemon.base import Document, RetrievedDocument


def test_mara_retrieve_expands_quick_ratio_queries(monkeypatch):
    calls = []

    def fake_retrieve(_self, message, history):
        calls.append((message, history))
        return [], []

    monkeypatch.setattr(FullQAPipeline, "retrieve", fake_retrieve)
    pipeline = MaraAgentPipeline(retrievers=[])

    pipeline.retrieve(
        "Does 3M have a healthy liquidity profile based on quick ratio?",
        [],
    )

    assert "Total current assets" in calls[0][0]
    assert "Total current liabilities" in calls[0][0]
    assert "Inventories" in calls[0][0]


def test_mara_retrieve_reuses_cache_for_formatted_generation_prompt():
    docs = [
        RetrievedDocument(
            text="Revenue increased in 2026.",
            id_="doc-1",
            metadata={"file_id": "file-1", "page_label": "3"},
        )
    ]
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline._mara_cached_retrieval = ("What happened?", [], docs, [])

    returned_docs, returned_info = pipeline.retrieve(
        "What happened?\n\nAnswer formatting requirements:\n- Return Markdown.",
        [],
    )

    assert returned_docs == docs
    assert returned_info == []


def test_mara_text_generation_disables_inner_claim_verification(monkeypatch):
    captured_kwargs = {}

    def fake_stream(_self, _message, _conv_id, _history, **kwargs):
        captured_kwargs.update(kwargs)
        yield Document(channel="chat", content="Revenue increased in 2026.")
        return Document(channel="chat", content="Revenue increased in 2026.")

    monkeypatch.setattr(FullQAPipeline, "stream", fake_stream)
    pipeline = MaraAgentPipeline(retrievers=[])

    answer, _events = _collect_text_rag_generation(
        pipeline,
        "What happened?",
        "conv-1",
        [],
        {"enable_claim_verification": True},
    )

    assert answer == "Revenue increased in 2026."
    assert captured_kwargs["enable_claim_verification"] is False


def test_mara_evidence_metadata_recovers_page_backrefs_from_nested_metadata():
    docs = [
        RetrievedDocument(
            text="Total current liabilities were $10,936 million.",
            id_="doc-1",
            metadata={
                "metadata": {
                    "file_id": "file-1",
                    "file_name": "3M_2023Q2_10Q.pdf",
                    "page_label": "4",
                }
            },
        )
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["text"]},
    )

    assert metadata["page_coverage"] == ["4"]
    assert metadata["source_ids"] == ["file-1"]
    assert metadata["evidence"][0]["page_label"] == "4"
    assert metadata["evidence"][0]["source_backrefs"] == ["file-1#page:4"]
