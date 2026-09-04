from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning import mara_qasper_candidate_request as candidate_request_module
from ktem.reasoning.mara_qasper_candidate import (
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    qasper_candidate_response_format,
)
from ktem.reasoning.mara_qasper_candidate_identity import candidate_digest
from ktem.reasoning.mara_qasper_candidate_request import fit_candidate_request
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)


class _CompactingTokenizer:
    def get_num_tokens_from_messages(self, messages: Any) -> int:
        user_content = str(messages[-1].content)
        return (
            QASPER_CANDIDATE_INPUT_TOKEN_BUDGET + 1
            if "[E2]" in user_content
            else QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
        )

    def get_num_tokens(self, text: str) -> int:
        return 0


class _BudgetLLM:
    def __init__(self, tokenizer: _CompactingTokenizer) -> None:
        self.tokenizer = tokenizer

    def get_num_tokens_from_messages(self, messages: Any) -> int:
        return self.tokenizer.get_num_tokens_from_messages(messages)

    def get_num_tokens(self, text: str) -> int:
        return self.tokenizer.get_num_tokens(text)


def _pack_request(question: str) -> SimpleNamespace:
    return SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan={
            "answer_type": "boolean",
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "description": "complete proposition support",
                    "required_for_verification": True,
                    "evidence_ids": [],
                    "evidence_refs": [],
                }
            ],
        },
    )


def _pack_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "chunk-1",
                "source_id": "paper",
                "text": "The authors compared the two systems.",
            }
        ],
    )


def _canonical_records() -> list[dict[str, Any]]:
    question = "Did the authors compare the two systems?"
    text_1 = "The authors compared the two systems."
    text_2 = "The authors compared the two systems again."
    return prepare_qasper_canonical_records(
        question,
        [
            {
                "label": "E1",
                "evidence_id": "aligned-1",
                "text": text_1,
                "text_start": 0,
                "selectors": [
                    {
                        "selector_id": "E1:S1",
                        "text": text_1,
                        "span_start": 0,
                        "span_end": len(text_1),
                    }
                ],
            },
            {
                "label": "E2",
                "evidence_id": "aligned-2",
                "text": text_2,
                "text_start": 0,
                "selectors": [
                    {
                        "selector_id": "E2:S1",
                        "text": text_2,
                        "span_start": 0,
                        "span_end": len(text_2),
                    }
                ],
            },
        ],
        candidate_transaction_id="candidate-transaction-1",
    )


def test_candidate_request_reprojects_canonical_records_after_budget_drop(
    monkeypatch,
) -> None:
    question = "Did the authors compare the two systems?"
    records = _canonical_records()
    observed: list[list[str]] = []
    original = candidate_request_module.prepare_qasper_canonical_records_with_trace

    def recording_prepare(
        question: str,
        records: list[dict[str, Any]],
        *,
        candidate_transaction_id: str = "",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        observed.append([str(record.get("evidence_id") or "") for record in records])
        return original(
            question, records, candidate_transaction_id=candidate_transaction_id
        )

    monkeypatch.setattr(
        candidate_request_module,
        "prepare_qasper_canonical_records_with_trace",
        recording_prepare,
    )
    (
        selected,
        diagnostics,
        messages,
        _measurement,
        dropped_count,
    ) = fit_candidate_request(
        _BudgetLLM(_CompactingTokenizer()),
        question,
        records,
        {
            "canonical_projection_required": True,
            "required_slots": [],
            "pre_request_dropped_evidence_count": 0,
        },
        response_schema=qasper_candidate_response_format(),
        controlled_candidate="",
        candidate_transaction_id="candidate-transaction-1",
    )

    assert dropped_count == 1
    assert [record["evidence_id"] for record in selected] == ["aligned-1"]
    assert observed == [["aligned-1"]]
    assert diagnostics["candidate_message_records_digest"] == candidate_digest(selected)
    assert len(messages) == 2


def test_freeze_rejects_candidate_message_record_receipt_mismatch() -> None:
    question = "Did the authors compare the two systems?"
    request = _pack_request(question)
    bundle = _pack_bundle()
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    records = prepare_qasper_canonical_records(question, source.records)

    with pytest.raises(
        ValueError,
        match="canonical_semantic_pack_candidate_records_mismatch",
    ):
        freeze_qasper_canonical_semantic_pack(
            bundle,
            question=question,
            slots=slots,
            source_packing=source,
            records=records,
            candidate_transaction_id="candidate-transaction-1",
            candidate_records_digest="tampered-record-receipt",
        )
