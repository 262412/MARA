from pathlib import Path
from types import SimpleNamespace
from typing import Any

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.docqa_image_documents import element_index_records_from_documents
from benchmark.schemas import BenchmarkDocument
from benchmark.task_answer_contracts import apply_task_answer_contract


class _VerifierLLM:
    def __call__(self, _prompt: str, **_kwargs):
        return SimpleNamespace(
            text='{"verdict":"insufficient_evidence","evidence_quote":""}'
        )


def test_benchmark_element_adapter_preserves_atomic_fields(tmp_path: Path):
    path = tmp_path / "report_page_7.png"
    path.write_bytes(b"png")
    shared = {
        "evidence_id": "table-parent",
        "element_id": "table-parent",
        "element_type": "table",
        "table_id": "income-statement",
        "row_label": "Revenue",
        "period_kind": "fiscal_year",
        "unit": "currency",
        "scale": "million",
        "currency": "USD",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
    }
    records = element_index_records_from_documents(
        [
            BenchmarkDocument(
                document_id="report",
                path=path,
                format_type="png",
                modality="page_image",
                metadata={
                    "page": 7,
                    "layout_elements": [
                        {
                            **shared,
                            "cell_id": "revenue-2022",
                            "column_label": "2022",
                            "period": "2022",
                            "value": "100",
                            "text": "Revenue 2022 100",
                        },
                        {
                            **shared,
                            "cell_id": "revenue-2023",
                            "column_label": "2023",
                            "period": "2023",
                            "value": "120",
                            "text": "Revenue 2023 120",
                        },
                    ],
                },
            )
        ]
    )

    assert [record["cell_id"] for record in records] == [
        "revenue-2022",
        "revenue-2023",
    ]
    assert records[0]["evidence_level"] == "cell"
    assert records[0]["row_label"] == "Revenue"
    assert records[0]["period"] == "2022"
    assert records[0]["value"] == "100"
    assert records[0]["scale"] == "million"


def test_qasper_answer_change_invalidates_verification_state():
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_type": "boolean",
        "structured_citations": [{"source_id": "paper", "page_label": "2"}],
        "predicted_citations": ["paper#page:2"],
        "evidence_metadata": {
            "evidence": [{"text": "No relevant statement.", "source_id": "paper"}],
            "verified_evidence": [{"evidence_id": "old"}],
            "verify_decision": {"status": "supported"},
            "claim_verification": [{"status": "supported"}],
            "guardrail_decision": {"status": "ok"},
            "verifier_observability": {"supported": 1},
        },
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=_VerifierLLM,
    )

    for key in (
        "verified_evidence",
        "verify_decision",
        "claim_verification",
        "guardrail_decision",
        "verifier_observability",
    ):
        assert key not in prediction["evidence_metadata"]


def test_canonical_citation_resolves_source_and_page_together():
    verified = {
        "evidence_id": "runtime-hit",
        "source_id": "runtime-b",
        "source_aliases": ["document-b"],
        "page_label": "5",
        "text": "The answer.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": "The answer.",
        "answer_type": "extractive",
        "evidence_bundle": {
            "items": [verified],
            "metadata": {"verified_claim_support_evidence": [verified]},
        },
        "predicted_sources": [
            "document-a#page:5",
            "document-b#page:5",
        ],
        "gold_evidence": [{"source_id": "document-b", "page_label": "5"}],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="mmdocrag",
        mode="scoring_adapter_v1",
    )

    assert prediction["structured_citations"][0]["source_id"] == "document-b"
