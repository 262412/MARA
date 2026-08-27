from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY,
)
from ktem.reasoning.mara_qasper_semantic_pack import load_qasper_canonical_semantic_pack

from scripts.slurm.qasper_debug_contract_support import _mapping, terminal_metadata

_PACK_CONTRACT = "qasper_canonical_semantic_pack.v1"


def canonical_semantic_pack_alignment_valid(prediction: dict[str, Any]) -> bool:
    metadata = terminal_metadata(prediction)
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    generator = _mapping(metadata.get("qasper_candidate_generation"))
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    if not _pack_identity_valid(pack, question=str(prediction.get("question") or "")):
        return False
    expected = {
        "semantic_pack_digest": str(pack.get("semantic_pack_digest") or ""),
        "span_universe_digest": str(pack.get("span_universe_digest") or ""),
        "candidate_transaction_id": str(pack.get("candidate_transaction_id") or ""),
    }
    if not all(expected.values()):
        return False
    if not _generator_identity_valid(generator, expected, pack):
        return False
    if not _verifier_identity_valid(verifier, expected):
        return False
    authority = _mapping(metadata.get("semantic_proposition_authority"))
    if authority.get("status") in {"verified", "insufficient", "rejected"} and not (
        _authority_identity_valid(authority, expected)
    ):
        return False
    return True


def _pack_identity_valid(pack: dict[str, Any], *, question: str) -> bool:
    if pack.get("contract_id") != _PACK_CONTRACT or not question.strip():
        return False
    bundle = EvidenceBundle(
        route="contract_audit",
        metadata={QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY: deepcopy(pack)},
    )
    loaded, reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id=str(pack.get("candidate_transaction_id") or ""),
    )
    return loaded is not None and not reason


def _generator_identity_valid(
    generator: dict[str, Any],
    expected: dict[str, str],
    pack: dict[str, Any],
) -> bool:
    return bool(
        generator.get("canonical_semantic_pack_digest")
        == expected["semantic_pack_digest"]
        and generator.get("canonical_span_universe_digest")
        == expected["span_universe_digest"]
        and generator.get("transaction_id") == expected["candidate_transaction_id"]
        and generator.get("canonical_pack_candidate_transaction_id")
        == expected["candidate_transaction_id"]
        and generator.get("candidate_evidence_set_binding")
        == pack.get("proposition_binding")
        and generator.get("required_slots") == pack.get("slots")
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
