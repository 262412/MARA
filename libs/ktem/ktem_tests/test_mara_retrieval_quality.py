from types import SimpleNamespace

from ktem.reasoning.mara import (
    MaraAgentPipeline,
    _collect_text_rag_generation,
    _message_with_answer_format_requirements,
)
from ktem.reasoning.mara_retrieval_query import retrieval_query
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


def test_finance_retrieval_query_expands_capex_cash_flow_questions():
    query = retrieval_query(
        "What is the FY2018 capital expenditure amount for 3M? "
        "Use the cash flow statement."
    )

    assert "Consolidated Statement of Cash Flows" in query
    assert "Capital expenditures" in query
    assert "Purchases of property, plant and equipment" in query


def test_finance_retrieval_query_expands_ppne_balance_sheet_questions():
    query = retrieval_query(
        "What is the year end FY2018 net PPNE for 3M? "
        "Use information shown in the balance sheet."
    )

    assert "Consolidated Balance Sheet" in query
    assert "Property, plant and equipment" in query
    assert "Accumulated depreciation" in query


def test_finance_retrieval_query_expands_segment_growth_questions():
    query = retrieval_query(
        "If we exclude the impact of M&A, which segment dragged down "
        "3M's overall growth in 2022?"
    )

    assert "Worldwide Sales Change" in query
    assert "Organic sales" in query
    assert "Acquisitions" in query
    assert "Divestitures" in query


def test_finance_retrieval_query_expands_capital_intensity_questions():
    query = retrieval_query("Is 3M a capital-intensive business based on FY2022 data?")

    assert "Consolidated Statement of Income" in query
    assert "Consolidated Balance Sheet" in query
    assert "Consolidated Statement of Cash Flows" in query
    assert "Property, plant and equipment" in query


def test_finance_retrieval_query_expands_net_ar_balance_sheet_questions():
    query = retrieval_query(
        "What is Amcor's year end FY2020 net AR (in USD millions)? "
        "Use the details shown within the balance sheet."
    )

    assert "Consolidated Balance Sheet" in query
    assert "Trade receivables, net" in query
    assert "Accounts receivable" in query
    assert "Property, plant and equipment" not in query


def test_finance_retrieval_query_expands_customer_and_geography_questions():
    customer_query = retrieval_query(
        "Who are the primary customers of Boeing as of FY2022?"
    )
    geography_query = retrieval_query(
        "What are the geographies that American Express primarily operates in as of 2022?"
    )

    assert "commercial airlines" in customer_query
    assert "U.S. government contracts" in customer_query
    assert "revenues from a limited number" in customer_query
    assert "geographic regions" in geography_query
    assert "United States" in geography_query
    assert "EMEA" in geography_query


def test_finance_retrieval_query_expands_dpo_and_restructuring_questions():
    dpo_query = retrieval_query(
        "What is FY2018 days payable outstanding (DPO) for Walmart? "
        "Please base your judgments on the statement of financial position "
        "and the P&L statement."
    )
    restructuring_query = retrieval_query(
        "What is the quantity of restructuring costs directly outlined in "
        "AES Corporation's income statements for FY2022?"
    )

    assert "Consolidated Statements of Income" in dpo_query
    assert "Consolidated Balance Sheets" in dpo_query
    assert "Accounts payable" in dpo_query
    assert "Cost of sales" in dpo_query
    assert "Consolidated Statements of Operations" in restructuring_query
    assert "Restructuring costs" in restructuring_query


def test_finance_retrieval_query_expands_major_acquisition_questions():
    query = retrieval_query(
        "What are major acquisitions that AMCOR has done in FY2023, FY2022 and FY2021?"
    )

    assert "acquisition" in query
    assert "acquisitions" in query
    assert "completed the acquisition" in query


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


def test_mara_text_generation_disables_multimodal_payloads(monkeypatch):
    observed_use_multimodal = []

    def fake_stream(_self, _message, _conv_id, _history, **_kwargs):
        observed_use_multimodal.append(_self.answering_pipeline.use_multimodal)
        yield Document(channel="chat", content="Revenue increased in 2026.")
        return Document(channel="chat", content="Revenue increased in 2026.")

    monkeypatch.setattr(FullQAPipeline, "stream", fake_stream)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.answering_pipeline = SimpleNamespace(use_multimodal=True)

    answer, _events = _collect_text_rag_generation(
        pipeline,
        "What happened?",
        "conv-1",
        [],
        {},
    )

    assert answer == "Revenue increased in 2026."
    assert observed_use_multimodal == [False]
    assert pipeline.answering_pipeline.use_multimodal is True


def test_mara_text_generation_honors_chat_clear_event(monkeypatch):
    def fake_stream(_self, _message, _conv_id, _history, **_kwargs):
        yield Document(channel="chat", content="raw <think>draft</think>")
        yield Document(channel="chat", content=None)
        yield Document(channel="chat", content="Final answer")
        return Document(channel="chat", content="Final answer")

    monkeypatch.setattr(FullQAPipeline, "stream", fake_stream)
    pipeline = MaraAgentPipeline(retrievers=[])

    answer, _events = _collect_text_rag_generation(
        pipeline,
        "What happened?",
        "conv-1",
        [],
        {},
    )

    assert answer == "Final answer"


def test_mara_answer_format_requirements_prioritize_direct_final_answer():
    prompt = _message_with_answer_format_requirements(
        "Does 3M have a reasonably healthy liquidity profile?"
    )

    assert "Start with the direct final answer" in prompt
    assert "For financial calculation questions" in prompt
    assert "avoid extra tables" in prompt


def test_mara_text_generation_returns_final_answer_without_rendered_thought(
    monkeypatch,
):
    def fake_stream(_self, _message, _conv_id, _history, **_kwargs):
        yield Document(channel="chat", content="raw <think>draft</think>")
        yield Document(channel="chat", content=None)
        yield Document(
            channel="chat",
            content=(
                "<details><summary><span style='color:grey'>Thought</span>"
                "</summary><blockquote>draft</blockquote></details>\n\n"
                "Final answer: Revenue increased in 2026."
            ),
        )
        return Document(channel="chat", content="Revenue increased in 2026.")

    monkeypatch.setattr(FullQAPipeline, "stream", fake_stream)
    pipeline = MaraAgentPipeline(retrievers=[])

    answer, _events = _collect_text_rag_generation(
        pipeline,
        "What happened?",
        "conv-1",
        [],
        {},
    )

    assert answer == "Revenue increased in 2026."
    assert "<details" not in answer
    assert "Thought" not in answer


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


def test_mara_evidence_metadata_drops_large_image_payload_fields():
    docs = [
        RetrievedDocument(
            text="Rendered page text.",
            id_="page-image:file-1:4",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "type": "image",
                "image_origin": "data:image/png;base64,large-payload",
                "rendered_page_image": "data:image/png;base64,rendered-payload",
            },
        )
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["page_image"]},
    )

    evidence_metadata = metadata["evidence"][0]["metadata"]
    assert "image_origin" not in evidence_metadata
    assert "rendered_page_image" not in evidence_metadata
