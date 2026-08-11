from __future__ import annotations

from typing import Any

from .finance_citation_contract import (
    authoritative_verified_claim_support,
    citation_metadata_targets,
    clear_answer_citation_state,
    record_verified_claim_support,
    typed_calculation_is_verified,
)


def metadata_citations_allowed(
    dataset_name: str,
    prediction: dict[str, Any],
) -> bool:
    dataset = str(dataset_name or "").lower()
    if (
        "financebench" in dataset
        and prediction.get("finance_citation_authority_status") == "invalid"
    ):
        return False
    return bool(prediction.get("gold_evidence")) or any(
        family in dataset
        for family in ("financebench", "slidevqa", "mmdocrag", "vidore")
    )


def enforce_finance_citation_authority(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> None:
    if "financebench" not in str(dataset_name or "").strip().lower():
        return
    if typed_calculation_is_verified(prediction):
        prediction["finance_citation_authority_status"] = "verified_calculation"
        prediction["structured_citations"] = []
        prediction["predicted_citations"] = []
        return
    authority = authoritative_verified_claim_support(prediction)
    prediction["finance_citation_authority_status"] = (
        "verified_claim_support" if authority is not None else "invalid"
    )
    if authority is None:
        clear_answer_citation_state(prediction)
        return
    support, _plan = authority
    prediction["structured_citations"] = []
    prediction["predicted_citations"] = []
    record_verified_claim_support(prediction, support)
    for metadata in citation_metadata_targets(prediction):
        metadata["emitted_citation_evidence"] = []
        metadata["cited_evidence"] = []
