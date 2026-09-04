from __future__ import annotations

from copy import deepcopy

from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
    canonical_payload_digest,
    qasper_candidate_records_digest,
    qasper_canonical_span_universe_digest,
)

from .mara_semantic_proposition_packing import SemanticPropositionEvidencePacking


def pack_payload(
    packing: SemanticPropositionEvidencePacking,
    *,
    question: str,
    slots: list[dict[str, object]],
    proposition_binding: dict[str, object],
    candidate_transaction_id: str,
    candidate_records_digest: str = "",
) -> dict[str, object]:
    return {
        "contract_id": QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT,
        "candidate_transaction_id": str(candidate_transaction_id or ""),
        "question_digest": canonical_payload_digest(question.strip()),
        "semantic_pack_digest": packing.semantic_pack_digest,
        "span_universe_digest": qasper_canonical_span_universe_digest(packing.records),
        "records": deepcopy(packing.records),
        "slots": deepcopy(slots),
        "proposition_binding": deepcopy(proposition_binding),
        "proposition_binding_digest": str(
            proposition_binding.get("binding_digest") or ""
        ),
        "candidate_message_records_digest": qasper_candidate_records_digest(
            packing.records, candidate_records_digest
        ),
        "item_char_limit": packing.item_char_limit,
        "input_token_budget": packing.input_token_budget,
        "estimated_input_tokens": packing.estimated_input_tokens,
        "dropped_count": packing.dropped_count,
        "truncated_count": packing.truncated_count,
        "question_proposition": deepcopy(packing.question_proposition),
        "question_proposition_resolution": deepcopy(
            packing.question_proposition_resolution
        ),
        "immutable_after_candidate_generation": True,
    }
