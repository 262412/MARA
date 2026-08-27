from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.slurm.qasper_debug_contract_identity import _digest
from scripts.slurm.qasper_debug_contract_support import _mapping, terminal_metadata

_PACK_CONTRACT = "qasper_canonical_semantic_pack.v1"


def canonical_semantic_pack_alignment_valid(prediction: dict[str, Any]) -> bool:
    metadata = terminal_metadata(prediction)
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    generator = _mapping(metadata.get("qasper_candidate_generation"))
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    if not _pack_identity_valid(pack):
        return False
    expected = {
        "semantic_pack_digest": str(pack.get("semantic_pack_digest") or ""),
        "span_universe_digest": str(pack.get("span_universe_digest") or ""),
        "candidate_transaction_id": str(pack.get("candidate_transaction_id") or ""),
    }
    if not all(expected.values()):
        return False
    if not _generator_identity_valid(generator, expected):
        return False
    if not _verifier_identity_valid(verifier, expected):
        return False
    authority = _mapping(metadata.get("semantic_proposition_authority"))
    if authority.get("status") in {"verified", "insufficient", "rejected"} and not (
        _authority_identity_valid(authority, expected)
    ):
        return False
    return True


def _pack_identity_valid(pack: dict[str, Any]) -> bool:
    payload = deepcopy(pack)
    identity_digest = str(payload.pop("pack_identity_digest", "") or "")
    records = payload.get("records")
    return bool(
        pack.get("contract_id") == _PACK_CONTRACT
        and pack.get("immutable_after_candidate_generation") is True
        and identity_digest
        and _digest(payload) == identity_digest
        and isinstance(records, list)
        and pack.get("span_universe_digest") == _span_universe_digest(records)
    )


def _span_universe_digest(records: list[Any]) -> str:
    universe = [
        {
            "evidence_id": str(record.get("evidence_id") or ""),
            "selector_id": str(selector.get("selector_id") or ""),
            "text": str(selector.get("text") or ""),
            "span_start": selector.get("span_start"),
            "span_end": selector.get("span_end"),
            "canonical_start": selector.get("canonical_start"),
            "canonical_end": selector.get("canonical_end"),
            "allowed_proposition_slots": list(
                selector.get("allowed_proposition_slots") or []
            ),
            "relation_bearing": selector.get("relation_bearing"),
            "candidate_relation_role": str(
                selector.get("candidate_relation_role") or ""
            ),
            "local_relation_state": str(selector.get("local_relation_state") or ""),
            "local_relation_analysis_digest": str(
                selector.get("local_relation_analysis_digest") or ""
            ),
        }
        for record in records
        if isinstance(record, dict)
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
    ]
    return _digest(universe)


def _generator_identity_valid(
    generator: dict[str, Any],
    expected: dict[str, str],
) -> bool:
    return bool(
        generator.get("canonical_semantic_pack_digest")
        == expected["semantic_pack_digest"]
        and generator.get("canonical_span_universe_digest")
        == expected["span_universe_digest"]
        and generator.get("transaction_id") == expected["candidate_transaction_id"]
        and generator.get("canonical_pack_candidate_transaction_id")
        == expected["candidate_transaction_id"]
    )


def _verifier_identity_valid(
    verifier: dict[str, Any],
    expected: dict[str, str],
) -> bool:
    return bool(
        verifier.get("semantic_pack_digest") == expected["semantic_pack_digest"]
        and verifier.get("canonical_span_universe_digest")
        == expected["span_universe_digest"]
        and verifier.get("candidate_transaction_id")
        == expected["candidate_transaction_id"]
        and verifier.get("canonical_pack_continuity_status") == "preserved"
        and _mapping(verifier.get("auditor_semantic_pack_identity")) == expected
    )


def _authority_identity_valid(
    authority: dict[str, Any],
    expected: dict[str, str],
) -> bool:
    return bool(
        authority.get("semantic_pack_digest") == expected["semantic_pack_digest"]
        and authority.get("canonical_span_universe_digest")
        == expected["span_universe_digest"]
        and authority.get("candidate_transaction_id")
        == expected["candidate_transaction_id"]
        and authority.get("canonical_pack_continuity_status") == "preserved"
        and _mapping(authority.get("auditor_semantic_pack_identity")) == expected
    )
