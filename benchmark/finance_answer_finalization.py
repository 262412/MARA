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
    if "qasper" in dataset:
        return bool(prediction.get("gold_evidence")) or _verified_qasper_plan(
            prediction
        )
    return bool(prediction.get("gold_evidence")) or any(
        family in dataset
        for family in (
            "financebench",
            "slidevqa",
            "mmdocrag",
            "vidore",
            "ragtruth",
        )
    )


def _verified_qasper_plan(prediction: dict[str, Any]) -> bool:
    for metadata in _metadata_sources(prediction):
        authority = metadata.get("semantic_proposition_authority")
        pack = metadata.get("qasper_canonical_semantic_pack")
        if not isinstance(authority, dict) or not isinstance(pack, dict):
            continue
        plan_id = str(authority.get("canonical_evidence_plan_id") or "").strip()
        plan_digest = str(
            authority.get("canonical_plan_digest")
            or authority.get("canonical_evidence_plan_digest")
            or ""
        ).strip()
        premise_count = authority.get("premise_count")
        if (
            authority.get("status") == "verified"
            and plan_id
            and plan_digest
            and isinstance(premise_count, int)
            and premise_count > 0
            and _pack_contains_plan(pack, plan_id)
        ):
            return True
    return False


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    values = [
        prediction.get("evidence_metadata"),
        _nested_metadata(prediction.get("evidence_bundle")),
        _nested_metadata(prediction.get("engine_terminal_evidence_bundle")),
    ]
    return [value for value in values if isinstance(value, dict)]


def _nested_metadata(value: Any) -> dict[str, Any] | None:
    return value.get("metadata") if isinstance(value, dict) else None


def _pack_contains_plan(pack: dict[str, Any], plan_id: str) -> bool:
    binding = pack.get("proposition_binding")
    canonical = (
        binding.get("canonical_evidence_plan") if isinstance(binding, dict) else None
    )
    if not isinstance(canonical, dict):
        return False
    return any(
        isinstance(plan, dict) and str(plan.get("plan_id") or "") == plan_id
        for plan in (
            canonical.get("support_plan"),
            canonical.get("contradiction_plan"),
        )
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
